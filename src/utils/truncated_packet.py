from scapy.all import IP, TCP, UDP, rdpcap


class TruncatedPacket:
    def __init__(
        self,
        packet_id,
        timestamp,
        size,
        pseudo_hash,
        flow_id,
        direction,
        src_ip,
        fragmented,   
        tcp,
        udp,
        fin,
        syn,
        rst,
        ack,
        psh,
        urg,
    ):
        self.packet_id = packet_id
        self.timestamp = timestamp
        self.size = size
        self.pseudo_hash = pseudo_hash
        self.flow_id = flow_id
        self.direction = direction
        self.src_ip = src_ip
        self.fragmented = fragmented
        self.tcp = tcp
        self.udp = udp
        self.fin = fin
        self.syn = syn
        self.rst = rst
        self.ack = ack
        self.psh = psh
        self.urg = urg

    def __repr__(self):
        return (
            f"TruncatedPacket(packet_id={self.packet_id}, timestamp={self.timestamp}, size={self.size}, "
            f"pseudo_hash='{self.pseudo_hash}', flow_id={self.flow_id}, direction='{self.direction}', src_ip={self.src_ip}, fragmented={self.fragmented}, "
            f"tcp={self.tcp}, udp={self.udp}, fin={self.fin}, syn={self.syn}, rst={self.rst}, ack={self.ack}, psh={self.psh}, urg={self.urg})"
        )


def generate_pseudo_hash(entity):
    elements = []

    if entity.haslayer(TCP):
        elements = [
            hash(entity[IP].src),
            hash(entity[IP].dst),
            int(entity[TCP].sport), #TODO: PRZYWROCIC
            int(entity[TCP].dport),
            int(entity[IP].proto),
        ]
    elif entity.haslayer(UDP):
        elements = [
            hash(entity[IP].src),
            hash(entity[IP].dst),
            int(entity[UDP].sport),
            int(entity[UDP].dport),
            int(entity[IP].proto),
        ]

    return int(sum(elements)) if elements else None  # Returns the sum of 'elements' or None if the list is empty


def create_truncated_packets_from_pcap(file_path):
    truncated_packets = []
    cap = rdpcap(file_path)

    for packet_number, scapy_packet in enumerate(cap, start=1):
        if IP in scapy_packet and (
            scapy_packet.haslayer(TCP) or scapy_packet.haslayer(UDP)
        ):
            pseudo_hash = generate_pseudo_hash(scapy_packet)

            tcp, udp, fin, syn, rst, ack, psh, urg = (
                0,
            ) * 8  # Initialize all flags to 0

            if scapy_packet.haslayer(TCP):
                tcp = 1
                flags = scapy_packet[TCP].flags
                fin = int(bool(flags & 0x01))
                syn = int(bool(flags & 0x02))
                rst = int(bool(flags & 0x04))
                ack = int(bool(flags & 0x10))
                psh = int(bool(flags & 0x08))
                urg = int(bool(flags & 0x20))

            udp = int(scapy_packet.haslayer(UDP))

            truncated_packet = TruncatedPacket(
                packet_id=packet_number,  # According to schema
                timestamp=scapy_packet.time,  # Timestamp will need to have margin of error
                size=len(scapy_packet),
                pseudo_hash=pseudo_hash,
                flow_id=None,  # Later assignment
                direction=0,  # 0 - not yet analyzed, 1 - fwd, 2 - bwd
                src_ip=scapy_packet[IP].src,
                fragmented=0, # 0 for non-fragmented, 1 - for signle fragmentation (MTU = size/2), 2 - for double fragmentation (MTU = size/4)
                tcp=tcp,
                udp=udp,
                fin=fin,
                syn=syn,
                rst=rst,
                ack=ack,
                psh=psh,
                urg=urg,
            )
            truncated_packets.append(truncated_packet)
            

    return truncated_packets

def count_directions(truncated_packets, flow_id):
    direction_counts = {"1": 0, "2": 0}
    for packet in truncated_packets:
        if packet.flow_id == flow_id:
            # Ensure the direction is treated as a string
            direction_str = str(packet.direction)
            direction_counts[direction_str] += 1
    return direction_counts
from collections import defaultdict
import random

# TODO: below not working properly and not used (for now)
def undersample_flows_with_distribution(truncated_packets, flow_num):
    """
    Randomly reduce the total number of unique flow IDs while attempting to preserve the original packet count distribution
    across the flows. Flows with more packets are more likely to be selected.

    Args:
    - truncated_packets: List of TruncatedPacket objects.
    - flow_num: The desired maximum number of unique flow IDs to keep.

    Returns:
    - A list of TruncatedPacket objects filtered to include only the desired number of unique flow IDs, attempting to preserve
      the original distribution of packet counts per flow.
    """
    # Count packets per flow_id
    flow_counts = defaultdict(int)
    for packet in truncated_packets:
        flow_counts[packet.flow_id] += 1

    # If we have fewer or equal unique flows than flow_num, no need to undersample
    if len(flow_counts) <= flow_num:
        return truncated_packets

    # Prepare for weighted sampling
    flows, weights = zip(*flow_counts.items())
    total_packets = sum(weights)
    weights_normalized = [count / total_packets for count in weights]

    # Select flow_ids based on their weight (packet count)
    selected_flows = set(random.choices(flows, weights=weights_normalized, k=flow_num))

    # Filter packets to keep only those within selected flows
    filtered_packets = [packet for packet in truncated_packets if packet.flow_id in selected_flows]

    return filtered_packets
