import os
import multiprocessing
from datetime import datetime

from . import recs_files


def pcap_writer_worker(
        pcap_queue: multiprocessing.Queue,
        logging_queue: multiprocessing.Queue,
        logger_name: str,
        recordings_path: str
):
    """
    Multiprocessing worker that receives pcap data from a queue and writes
    to per-engine daily pcapng files with thread_id comments.
    """
    from ..wrappers.loggingw import loggingw

    # Set up logging with QueueHandler (same pattern as _create_tcp_server_process).
    _ = loggingw.create_logger(
        logger_name=logger_name,
        add_queue_handler=True,
        log_queue=logging_queue,
    )
    logger = loggingw.get_logger_with_level(f'{logger_name}.pcap_writer')

    # Suppress scapy import warning.
    import logging as _logging
    _logging.getLogger("scapy.loading").setLevel(_logging.ERROR)
    from scapy.layers.inet import IP, TCP
    from scapy.packet import Raw
    from scapy.utils import PcapNgWriter
    from scapy.config import conf

    # {engine_dir: {'writer': PcapNgWriter, 'date': str, 'path': str}}
    writers: dict = {}

    # Per-connection TCP sequence tracking so Wireshark sees coherent streams.
    # Key: frozenset({(ip1, port1), (ip2, port2)})
    # Value: {(ip, port): seq_counter, ...}  — one seq counter per direction
    tcp_streams: dict = {}

    try:
        while True:
            msg = pcap_queue.get()

            # None = stop signal
            if msg is None:
                break

            engine_dir = msg['engine_dir']
            current_date = datetime.now().strftime(recs_files.REC_FILE_DATE_FORMAT)

            # Get or create writer, handle daily rotation
            writer_info = writers.get(engine_dir)
            if writer_info is None or writer_info['date'] != current_date:
                if writer_info is not None:
                    writer_info['writer'].close()
                pcap_file_path = f'{engine_dir}{os.sep}{current_date}.pcapng'
                append = os.path.exists(pcap_file_path) and os.path.getsize(pcap_file_path) > 0
                # PcapNgWriter always opens in "wb" (truncating). When appending,
                # construct on devnull to avoid destroying the existing file.
                writer = PcapNgWriter(os.devnull if append else pcap_file_path)
                if append:
                    writer.f.close()
                    writer.f = open(pcap_file_path, "ab", 4096)
                    writer.header_present = True
                    # write_header() won't run (header_present=True), so set linktype
                    # manually — scapy's write() needs it.
                    writer.linktype = conf.l2types.layer2num[IP]
                writer.sync = True
                writer_info = {'writer': writer, 'date': current_date, 'path': pcap_file_path}
                writers[engine_dir] = writer_info

            # Max payload per packet: 65000 bytes.
            # Keeps each packet under both the IP/TCP 16-bit field limit (65535)
            # and Wireshark's pcapng cap_len limit (262144).
            MAX_CHUNK = 65000

            raw_bytes = msg['raw_bytes']
            chunks = [raw_bytes[i:i + MAX_CHUNK] for i in range(0, len(raw_bytes), MAX_CHUNK)]
            total_chunks = len(chunks)

            # Look up or initialize TCP stream state for this connection.
            src_ep = (msg['source_ip'], msg['source_port'])
            dst_ep = (msg['dest_ip'], msg['dest_port'])
            conn_key = frozenset({src_ep, dst_ep})
            if conn_key not in tcp_streams:
                tcp_streams[conn_key] = {src_ep: 1, dst_ep: 1}
            stream = tcp_streams[conn_key]

            for chunk_idx, chunk in enumerate(chunks):
                current_seq = stream[src_ep]
                current_ack = stream[dst_ep]
                packet = IP(
                    src=msg['source_ip'], dst=msg['dest_ip']
                ) / TCP(
                    sport=msg['source_port'], dport=msg['dest_port'],
                    seq=current_seq, ack=current_ack, flags='PA'
                ) / Raw(load=chunk)
                packet.time = msg['timestamp']

                comment = f"thread_id={msg['thread_id']}"
                if msg.get('process_name'):
                    comment += f" | process_cmdline={msg['process_name']}"
                if total_chunks > 1:
                    comment += f" | chunk={chunk_idx + 1}/{total_chunks}"
                packet.comments = [comment.encode()]

                writer_info['writer'].write(packet)
                stream[src_ep] += len(chunk)

            logger.info(f"Appended to pcap file: {writer_info['path']}")
    except KeyboardInterrupt:
        pass

    # Cleanup: close all writers
    for info in writers.values():
        try:
            info['writer'].close()
        except Exception:
            pass
