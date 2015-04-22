import socket

server_hostname = socket.gethostbyname(socket.gethostname())
server_port = 7736

client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

while 1:
    msg = input("Enter message: ")
    client_socket.sendto(bytes(msg, "utf-8"), (server_hostname, server_port))

    server_msg = str(client_socket.recv(1024), "utf-8")
    print("Server msg:", server_msg)