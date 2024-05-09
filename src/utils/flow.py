import scapy
from scapy.all import IP, TCP, UDP, rdpcap
from collections import defaultdict

TCP_EXPIRATION = 240  # 2x typical MSL (Maximum Segment Lifetime) for TCP
UDP_EXPIRATION = 240 # Sufficiently long for UDP

from collections import defaultdict

def assign_flow_ids_to_packets(truncated_packets):
    packets_by_hash = defaultdict(list)
    for packet in truncated_packets:
        if packet.pseudo_hash is not None:
            packets_by_hash[packet.pseudo_hash].append(packet)

    print(f"hash groups: {len(packets_by_hash.values())}")
    global_flow_id = 1
    flow_start_timestamp = {}  # Dictionary to store the initial timestamp for each flow
    first_packet_src_ip = None  # Reset at the beginning of processing

    fin_count = defaultdict(int)  # Tracks the number of FIN flags seen in each flow

    for hash_group in packets_by_hash.values():
        hash_group.sort(key=lambda pkt: pkt.timestamp)

        new_flow_needed = False

        for i, packet in enumerate(hash_group):
            if global_flow_id not in flow_start_timestamp:
                flow_start_timestamp[global_flow_id] = packet.timestamp
                first_packet_src_ip = packet.src_ip

            if i > 0:  # Calculate time since last packet if it's not the first packet
                time_since_last_packet = packet.timestamp - hash_group[i-1].timestamp
            else:
                time_since_last_packet = 0

            expiration_time = TCP_EXPIRATION if packet.tcp else UDP_EXPIRATION
            if time_since_last_packet >= expiration_time:
                new_flow_needed = True

            # Ensure the last packet in the group triggers a new flow for the next packet in another group
            if i == len(hash_group) - 1:
                new_flow_needed = True

            if new_flow_needed:
                global_flow_id += 1
                flow_start_timestamp[global_flow_id] = packet.timestamp
                first_packet_src_ip = packet.src_ip  # Start new flow with the current packet IP
                fin_count[global_flow_id] = 0  # Reset FIN counter for the new flow
                new_flow_needed = False

            # Flow will be completed AFTER processed packet
            if packet.fin:
                fin_count[global_flow_id] += 1
                if fin_count[global_flow_id] >= 2:
                    new_flow_needed = True

            packet.flow_id = global_flow_id
            packet.direction = 1 if packet.src_ip == first_packet_src_ip else 2


    return truncated_packets
