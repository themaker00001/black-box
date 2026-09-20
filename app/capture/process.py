import psutil

for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
    try:
        info=proc.info
        print(info)
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:  # this is for the psutil exception
        print(f"Skipping process: {type(e).__name__}")

    except Exception as e:    #this is hanling the exception we donot knwo anything about
        print(f"Unexpected error: {type(e).__name__}: {e}")