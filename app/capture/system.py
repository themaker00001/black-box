import psutil
import time 
#This the one which is going to give the suystem stats
cpu_cores=psutil.cpu_count(logical=False)
cpu_percent=psutil.cpu_percent()
virtual_memory=psutil.virtual_memory() # ram only 
swap_memory=psutil.swap_memory()
disk=psutil.disk_usage("/")
net = psutil.net_io_counters()

def net_speed(interval=1):
    a=psutil.net_io_counters()
    time.sleep(interval)
    b=psutil.net_io_counters()
    return{
        "sent":(b.bytes_sent-a.bytes_sent)/interval,
        "recived":(b.bytes_recv-a.bytes_recv)/interval # DIVIDED TO GET THE BYTE/SEC NOT HELPFUL NOW WILL BE ONCE WE INCREASE THE INTERVAL
    }
print(net_speed())  # WILL GIVE THE SPEED IN MBPS 
print(net.bytes_sent)
print(net.bytes_recv)
print(f"cpu_cores:{cpu_cores},cpu_percent:{cpu_percent}:{virtual_memory},swap_memory:{swap_memory},disk:{disk}")
