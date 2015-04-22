import socketserver
import socket

hostname = socket.gethostbyname(socket.gethostname())
port = 7736


class UDPServer(socketserver.BaseRequestHandler):
    def handle(self):

        client_request_str = self.request[0]
        conn_socket = self.request[1]
        conn_socket.sendto(client_request_str.upper(), self.client_address)


class FTPServer(socketserver.ThreadingMixIn, socketserver.UDPServer):
    pass

server = FTPServer((hostname, port), UDPServer)
server.serve_forever()