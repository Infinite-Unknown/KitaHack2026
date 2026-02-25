import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("192.168.8.155", 8080))
print("Listening for UDP on 192.168.8.155:8080...")
while True:
    data, addr = sock.recvfrom(1024)
    print(f"Received from {addr}: {data}")
