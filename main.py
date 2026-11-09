from pathlib import Path
import subprocess
import re
import math

#Reusable prompt code for number values
def get_number(prompt, default, minimum=None, maximum=None):

    while True:#creates an infinite loop until the prompt is valid
        user_input = input(prompt).strip()

        if user_input == "":#check if they entered nothing
            value = default
        else:
            #where I actually learned how to use a try-except block (first time in my life)
            try:#try their value to see if they entered a number
                value = float(user_input)

            except ValueError:#if they didn't enter a number
                print("Please enter a valid number.")
                continue#restart loop

        if not math.isfinite(value):#if they enter inputs like inf or nan
            print("Please enter a finite number.")
            continue#restart loop

        if minimum is not None and value < minimum:#if they enter a number less than minimum
            print(f"Value must be at least {minimum}.")
            continue#restart loop

        if maximum is not None and value > maximum:#if they enter a number greater than maximum
            print(f"Value must be no greater than {maximum}.")
            continue#restart loop

        return value #only reaches here if the value is valid

#-----------BEGIN CODE-----------#


#Get video path
video_path = Path(input("Provide the path for your video: "))
#check if video_path is actually a file
if (not video_path.is_file()):
    raise FileNotFoundError("The specified video file does not exist.")

#-------Prompts-------

#Prompt user for maximum noise level detected as silence
silence_db = get_number(
    "Noise threshold in dB (default -35): ",
    default=-35,
    minimum=-100,
    maximum=0
)
print(silence_db)

#Prompt user for duration of silences they want to cut
silence_duration = get_number(
    "Minimum silence duration in seconds (default 0.7): ",
    default=0.7,
    minimum=0.001
)
print(silence_duration)

#prompt for padding before the cut
padding_before = get_number(
    "Padding before a cut in seconds (default 0.1): ",
    default=0.1,
    minimum=0
)

#prompt for padding after the cut
padding_after = get_number(
    "Padding after a cut in seconds (default 0.2): ",
    default=0.2,
    minimum=0
)



result = subprocess.run(#allows Python to run ffmpeg commands in terminal and receive the output
    ["ffmpeg", "-i", str(video_path)],
    capture_output=True,
    text=True
)

#Get the video's duration
duration_line = next(#returns next item from iterator (next value found)
    line for line in result.stderr.splitlines()#for each line in the stderr string
    if "Duration:" in line #if this string is found in it
)

duration_text = duration_line.split("Duration: ")[1].split(",")[0]#gets the value of the string between "Duration: " and "," (the length of minutes)

hours, minutes, seconds = duration_text.split(":")#splits up the duration and gets the values for the hrs, mins, and secs

video_duration = (#converts the sum of the hrs, mins, and secs to solely seconds
    int(hours) * 3600
    + int(minutes) * 60
    + float(seconds)
)

print(video_duration)



# Detect silence in the video

process = subprocess.Popen(
    [
        "ffmpeg",
        "-i", str(video_path),
        "-af", f"silencedetect=noise={silence_db}dB:d={silence_duration}",
        "-f", "null", "-"
    ],
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1
)

ffmpeg_output = []

for line in process.stderr:
    print(line, end="")
    ffmpeg_output.append(line)

process.wait()
#Raise an error if FFmpeg didn't detect any silence
if process.returncode != 0:
    raise RuntimeError("FFmpeg silence detection failed.")

silences = []
current_start = None

for line in ffmpeg_output:
    #get the timestamps for the starts and ends of silences
    start_match = re.search(r"silence_start:\s*([0-9.]+)", line)
    end_match = re.search(r"silence_end:\s*([0-9.]+)", line)

    if start_match:#if there is a silence
        current_start = float(start_match.group(1))#make current_start it's timestamp

    elif end_match and current_start is not None:#if there is a start and end
        end = float(end_match.group(1))#make end equal to the end's timestamp

        silences.append({#add the silence duration to the silences list
            "start": current_start,
            "end": end,
            "duration": end - current_start
        })

        current_start = None #reset current_start to none so next loop can begin

if current_start is not None: #if we encountered a silence that occurs until the end of the video (so there isn't an ending timestamp for the silence)
    silences.append({ #add this silence to the silence list
        "start": current_start,
        "end": video_duration, #make the end of the video where the silence ends (because it should be a silence lasting until the end of the video)
        "duration": video_duration - current_start
    })

print(silences)
total_silence = sum(silence["duration"] for silence in silences)

remaining_duration = video_duration - total_silence



# -------Incorporate cuts in the video, getting rid of silence-------

#Where we will access the intervals of silence
cuts = []

#Add the moments of silence being cut (adjusted to have the padding) into the "cuts" list
for silence in silences:
    cut_start = max(0, silence["start"] + padding_before)
    cut_end = min(video_duration, silence["end"] - padding_after)

    # Discard invalid or empty cuts
    if cut_start >= cut_end:
        continue

    cuts.append({
        "start": cut_start,
        "end": cut_end,
        "duration": cut_end - cut_start
    })

#Merge all the cuts that might overlap
merged_cuts = []
cuts.sort(key=lambda cut: cut["start"])
for cut in cuts:
    if not merged_cuts or cut["start"] > merged_cuts[-1]["end"]:
        merged_cuts.append(cut.copy())

    else:
        merged_cuts[-1]["end"] = max(
            merged_cuts[-1]["end"],
            cut["end"]
        )

        merged_cuts[-1]["duration"] = (
            merged_cuts[-1]["end"] - merged_cuts[-1]["start"]
        )

cuts = merged_cuts

#Figure out what segments of the video we keep
segments_to_keep = []
current_time = 0.0

for cut in cuts:
    #Preserve the moments before the first cut
    if current_time < cut["start"]:
        segments_to_keep.append({
            "start": current_time,
            "end": cut["start"],
            "duration": cut["start"] - current_time
        })

    current_time = cut["end"]

# Preserve everything after the final cut
if current_time < video_duration:
    segments_to_keep.append({
        "start": current_time,
        "end": video_duration,
        "duration": video_duration - current_time
    })


#Validate results
total_cut_duration = sum(cut["duration"] for cut in cuts)

total_kept_duration = sum(
    segment["duration"] for segment in segments_to_keep
)

print(f"Number of cuts: {len(cuts)}")
print(f"Number of kept segments: {len(segments_to_keep)}")
print(f"Time removed: {total_cut_duration:.2f} seconds")
print(f"Time preserved: {total_kept_duration:.2f} seconds")
print(f"Original duration: {video_duration:.2f} seconds")
print(
    f"Duration difference: "
    f"{video_duration - total_cut_duration - total_kept_duration:.6f}"
)