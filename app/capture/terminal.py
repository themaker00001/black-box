import subprocess

traking_termianl_command=subprocess.run(['ls','-l'],capture_output=True,text=True)
print(traking_termianl_command)