import socket

s = socket.socket()
s.connect(("127.0.0.1", 11211))
s.sendall(b"set serverNum 0 0 1\r\n0\r\n")
print("Memcached serverNum counter initialization complete!")
