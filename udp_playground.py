#%%
import socket
import threading
local_ip = '10.123.1.32'
scanimage_port = 1001
global messagelist
messagelist = list()
def rec_UDP(ip,port):
    global messagelist
    while True:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((ip, port))
        data, addr = sock.recvfrom(1024)
        messagelist.append(data)
        #return data


# The thread that ables the listen for UDP packets is loaded
listen_UDP = threading.Thread(target=rec_UDP,args = [local_ip,scanimage_port])
listen_UDP.start()



# =============================================================================
# 
# sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
# sock.bind((scanimage_ip,scanimage_port))
# #while True:
# data, addr = sock.recvfrom(1024)
# print(data)
# =============================================================================
#%%
import socket
scanimage_ip = '10.123.1.119'
scanimage_port = 1002
MESSAGE = b"Hello, World!"
sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
sock.sendto(MESSAGE, (scanimage_ip, scanimage_port))