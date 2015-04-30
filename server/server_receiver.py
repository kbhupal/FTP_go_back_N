import socket
import pickle
import random
import sys

# Read the command line arguments
command_args = sys.argv
SERVER_PORT = int(command_args[1])
STORE_FILE_NAME = command_args[2]
PACKET_LOSS_PROB = float(command_args[3])

# Types of packets
TYPE_DATA = "0101010101010101"
TYPE_ACK = "1010101010101010"
TYPE_EOF = "1111111111111111"
DATA_PAD = "0000000000000000"

# Port for the acknowledgement server
ACK_PORT = 10000


# SERVER_PORT = 7736
# PACKET_LOSS_PROB = 0.2


# Send the acknowledgement packet
def send_acknowledgement(ack_packet, host):
    # Create a UDP socket for acknowledgement passing
    # print("ACK sent:",  )
    ack_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ack_socket.sendto(ack_packet, (host, ACK_PORT))
    ack_socket.close()


# checksum addition with carry bit
def carry_around_addition(num_1, num_2):
    c = num_1 + num_2
    return (c & 0xffff) + (c >> 16)


# Compute the checksum for a given data element
def compute_checksum(data):
    checksum = 0
    for i in range(0, len(data), 2):
        my_message = str(data)
        w = ord(my_message[i]) + (ord(my_message[i+1]) << 8)
        checksum = carry_around_addition(checksum, w)
    return (not checksum) & 0xffff


# Get the hostname and the port
hostname = socket.gethostname()


# Create a UDP Socket and bind
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_socket.bind((hostname, SERVER_PORT))

# print(socket.gethostbyname(socket.gethostname()))

# Filename to write the file to
# STORE_FILE_NAME = "/opt/temp/hw.txt"

next_seq_no = 0


while True:
    # Receive data from the client
    data, address = server_socket.recvfrom(65535)

    # print("data received")
    # Unserialize the received data
    data = pickle.loads(data)

    # Extract the fields from the object
    sequence_number, checksum, type, mss_data = data[0], data[1], data[2], data[3]
    # print(sequence_number, checksum, type, mss_data)

    # Check the type of packet
    if type == TYPE_EOF:
        # print("Received the file!")
        # print("Closing the socket")
        server_socket.close()
        break

    # If the data received is a 'data' packet
    if type == TYPE_DATA:
        # print("Data packet received", sequence_number)
        # Get a random number to predict the packet loss
        random_probability = random.random()

        # If psuedo packet loss,
        if random_probability < PACKET_LOSS_PROB:
            print("Packet loss, sequence number =" + str(sequence_number))

        # If not fake loss
        else:
            # print("next seq num:", next_seq_no)
            if checksum != compute_checksum(mss_data):
                # print("Packet dropped, checksum doesnt match, sequence number =" + str(sequence_number))
                pass
            if next_seq_no == sequence_number:
                # print("Data successfully stored", sequence_number)
                acknowledgement = sequence_number + 1
                ack_packet = [acknowledgement, DATA_PAD, TYPE_ACK]
                # print("ack num:", acknowledgement)
                # Serialize the ack packet
                ack_packet = pickle.dumps(ack_packet)
                send_acknowledgement(ack_packet, address[0])

                # Open the output file in append byte mode
                with open(STORE_FILE_NAME, 'ab') as file:
                        file.write(mss_data)

                next_seq_no += 1

            elif next_seq_no < sequence_number:
                # print("Havent Received sequence number" + str(next_seq_no))
                acknowledgement = next_seq_no
                ack_packet = [acknowledgement, DATA_PAD, TYPE_ACK]

                # Serialize the ack packet
                ack_packet = pickle.dumps(ack_packet)
                send_acknowledgement(ack_packet, address[0])
