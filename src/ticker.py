import threading

top_content = {'step': 0}

def printer(tick):
    print('Timer tick', tick, top_content)
    top_content['step'] += 1
    return True



def thread_interval(callback=None, timeout=60, f_stop=None, tick=-1):
    f_stop = f_stop or threading.Event()
    callback = callback or printer
    allow = callback(tick) or True
    tick += 1
    if allow is True and (not f_stop.is_set()):
        print('Start timer')
        # call f() again in 60 seconds
        threading.Timer(timeout, thread_interval, [callback, timeout, f_stop, tick]).start()

# start calling f now and every 60 sec thereafter
# thread_interval(printer, 5)
# thread_interval(printer, 3)

def start(timeout, callback=None, f_stop=None, tick=-1):
    return thread_interval(callback, timeout, f_stop, tick)
