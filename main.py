from pathlib import Path
import subprocess
video_path = Path("videos/the reason for the videos.mov")
print(video_path)
print(video_path.exists())

result = subprocess.run(#allows Python to run ffmpeg commands in terminal and receive the output
    ["ffmpeg", "-i", str(video_path)],
    capture_output=True,
    text=True
)

#Get the value for the duration
duration_line = next(#returns next item from iterator (next value found)
    line for line in result.stderr.splitlines()#for each line in the stderr string
    if "Duration:" in line #if this string is found in it
)

duration_text = duration_line.split("Duration: ")[1].split(",")[0]#gets the value of the string between "Duration: " and "," (the length of minutes)

hours, minutes, seconds = duration_text.split(":")#splits up the duration and gets the values for the hrs, mins, and secs

duration = (#converts the sum of the hrs, mins, and secs to solely seconds
    int(hours) * 3600
    + int(minutes) * 60
    + float(seconds)
)

print(duration)