import socket
import sys
import pickle
import signal
import threading
from multiprocessing import Lock
from collections import namedtuple


command_args = sys.argv
# TODO: Uncomment to read from the command lines args
# Get the server hostnames and port
# server_hostname = command_args[1]
SERVER_HOST = socket.gethostbyname(socket.gethostname())
# server_port = command_args[2]
SERVER_PORT = 7736

# Acknowledgement server hostname and port
ACK_HOST = socket.gethostname()
ACK_PORT = 10000

# Filename
# file_location = command_args[3]
file_location = "/home/falcon/helloworld.txt"
# file_location = "D:/image.jpg"

# Window Size N
# N = command_args[4]
N = 5

# MSS
# MSS = command_args[5]
MSS = 5

# Types of packets
TYPE_DATA = "0101010101010101"
TYPE_ACK = "1010101010101010"
TYPE_EOF = "1111111111111111"

# Create named tuples for the data packet and the ACK packet
data_packet = namedtuple('data_packet', 'sequence_no checksum type data')
ack_packet = namedtuple('ack_packet', 'sequence_no padding type')

# Create a lock object for synchronization purposes
thread_lock = Lock()

# The sliding window limits
# At the beginning, lower limit will be 0 and higher limit will be N - 1
window_floor = 0
window_ceil = N - 1

# Number of packets sent
piped_packet = 0

# Most recently received ACK
ACK = 0

# The RTT for the packets in seconds
RTT = 3

# Completion notifier
completed = False


# Compute the checksum for a given data element
def compute_checksum(data):
    return 0xfff


# Send a packet by sequence number
def send_packet(sequence_number):
    print("Sending packet =", sequence_number)

    # Send the packet with the given sequence number to the server
    client_socket.sendto(preprocessed_packet_data[sequence_number], (SERVER_HOST, SERVER_PORT))


# The signal handler for the signalling object
def signal_handler(signum, frame):
    global ACK, window_ceil, window_floor, RTT, packets_length

    # Start index of the sequence number which needs to be resent
    index = ACK
    # If the last received ACK is the current window lower limit
    if ACK == window_floor:
        # Print the given message
        print("Timeout, sequence number =", ACK)

        thread_lock.acquire()

        # For all the packets that are not acknowledged, resend those until the upper window limit
        while index < window_ceil and index < packets_length:
            # Reset the timer, and start it at REAL time
            signal.alarm(0)
            signal.setitimer(signal.ITIMER_REAL, RTT)
            send_packet(index)
            index += 1
        thread_lock.release()


# Get the file data as packets and perform the required preprocessing
def preprocess(mss_array):
    # Initialize the sequence number
    sequence_number = 0

    # Final Packets
    packets = list()

    # Construct the entire packet in the loop
    for mss_data in mss_array:
        packet_checksum = compute_checksum(mss_data)
        packet_attr_list = [sequence_number, packet_checksum, TYPE_DATA, mss_data]

        # Using the Python pickle library to serialize the list object created above, so this can be sent and opened
        # easily at the server side
        packet = pickle.dumps(packet_attr_list)

        # Add the above packet to the list of packets
        packets.append(packet)

        # Increment the sequence number for the next iteration
        sequence_number += 1

    return packets


# Read a file MSS byte at a time and return the byte array
def read_data(filename):
    mss_array = list()
    # Open the file in read_byte format
    with open(filename, "rb") as f:

        while True:
            # Read MSS bytes at a time
            mss_bytes = f.read(MSS)

            # If the content is not empty, append to the mss_array
            if mss_bytes:
                mss_array.append(mss_bytes)
            else:
                break

    return mss_array


# Send the packets that are created
def rdt_send(client_socket):
    global preprocessed_packet_data, packets_length, piped_packet

    # While the number of packets in the pipe is less than the current max window
    max_window = min(N, packets_length)
    while piped_packet < max_window:
        # Only the first batch of packets are sent from here, rest are handled by the acknowledgement handler
        if ACK == 0:
            send_packet(piped_packet)
            piped_packet += 1
        else:
            break


# Acknowledgement handler thread, since we cannot have a synchronous packet sending and ack receiving mechanism
def acknowledgement_handler():
    print("acknowledgement_handler started")
    global window_ceil, window_floor, packets_length, piped_packet, ACK, completed

    # Create a UDP server socket to listen for ACKs from the FTP server
    ack_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ack_sock.bind((ACK_HOST, ACK_PORT))
    # Listen forever, until the final ACK is received
    print("Starting listening for ACK packets on", ACK_HOST, ACK_PORT)
    while True:
        # Receive a ACK message from the server
        server_message = ack_sock.recv(65535)
        print("server message", server_message)
        fields = pickle.loads(server_message)
        print("ACK", fields)

        # Check if the type of message is ACK
        if fields[2] == TYPE_ACK:
            # Get the ACK number from fields[0]
            ACK = fields[0]
            # If ACK is a valid field
            if ACK:
                # synchronize
                thread_lock.acquire()

                # If received ACK is higher than the number of packets, implies all transferred
                if ACK == packets_length:
                    print("All packets sent!")
                    thread_lock.release()
                    completed = True
                    break

                # Check the ACK limits
                elif packets_length > ACK >= window_floor:
                    # Reset the timer
                    signal.alarm(0)
                    signal.setitimer(signal.ITIMER_REAL, RTT)

                    # Number of ACKed packets
                    number_of_acked = ACK - window_floor
                    window_floor = ACK

                    # Update the window ceiling
                    outdate_ceil = window_ceil
                    window_ceil = min(window_ceil + number_of_acked, packets_length - 1)

                    # Send out new packets that have seq number between old_ceil and new window_ceil
                    # Using window_ceil - outdate_ceil because the number_of_acked doesn't always give the right remaining packets
                    for i in range(window_ceil - outdate_ceil):
                        send_packet(piped_packet)
                        if piped_packet < packets_length - 1:
                            piped_packet += 1

                    thread_lock.release()


# Create a UDP client socket
client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Get the mss_byte_array of the given file
mss_byte_array = read_data(file_location)

# Pre-process the mss_byte_array data so that each packet is completely constructed
# It should contain the seq_no associated with the packets, its checksum and the type
# This contains the entire header fields and the data
preprocessed_packet_data = preprocess(mss_byte_array)

# Get the length of the number of packets
packets_length = len(preprocessed_packet_data)

# Update the upper window limit, incase the length of packets is less that the provided window size
window_ceil = min(N, packets_length) - 1

# Create a cross-thread signal object to act like the timer for receiving ACKs
signal.signal(signal.SIGALRM, signal_handler)

# Start the ACK thread
acknowledgement_thread = threading.Thread(target=acknowledgement_handler)
acknowledgement_thread.start()

# Send the packets to the server
rdt_send(client_socket)


# Do nothing until not completed
while not completed:
    pass

# Once complete, close the acknowledge thread
acknowledgement_thread.join()
client_socket.close()