import os
import qrcode
import cv2
import argparse
import matplotlib.pyplot as plt
import numpy as np
import subprocess
import signal
import sys
import time

from concurrent.futures import ThreadPoolExecutor
from math import log10, sqrt

ffmpeg_path = "ffmpeg"
mahimahi_path = ""
fps = 30

def gen_qrcode_pic(num, data_dir):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=6,
        border=1,
    )
    qr.add_data(str(num))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(data_dir + "/qrcode_"+str(num)+".png")

def gen_qrcode(cfg, num):
    data_dir = "../qrcode/"+cfg.data
    os.system("rm -rf " + data_dir)
    os.system("mkdir -p " + data_dir)

    for i in range(1, num+1):
        gen_qrcode_pic(i, data_dir)
    ffmpeg_command = ffmpeg_path + " -f image2 -r "+ str(fps) +" -i " + data_dir + "/qrcode_%d.png -pix_fmt yuv420p " + data_dir + "/qrcode_output.yuv -y"

    os.system(ffmpeg_command)

def overlay_qrcode_to_video(cfg):
    video_path = "../data/" + cfg.data + ".yuv"

    file_stats = os.stat(video_path)
    i420_frame_size = 3 * cfg.width * cfg.height / 2
    frame_count = int(file_stats.st_size / i420_frame_size)

    print(f'Frame count: {frame_count}')

    gen_qrcode(cfg, frame_count)

    send_pic = "../send/" + cfg.data

    os.system("rm -rf "+send_pic)
    os.system("mkdir -p "+send_pic)

    qrcode_path = "../qrcode/" + cfg.data + "/qrcode_output.yuv"
    output_path = "../data/" + cfg.data + "_qrcode.yuv"
    ffmpeg_command = ffmpeg_path + " -s " + str(cfg.width) + "x" + str(cfg.height) + " -i " +\
                        video_path + " -s 138x138 -i " +\
                        qrcode_path + " -s 138x138 -i " +\
                        qrcode_path + " -s 138x138 -i " +\
                        qrcode_path + " -filter_complex \"[0][1]overlay=30:30[v1]; " +\
                                        "[v1][2]overlay=960:30[v2]; " +\
                                        "[v2][3]overlay=1700:30[v3]\" -map \"[v3]\" " +\
                        output_path + " -y"
    print(ffmpeg_command)
    os.system(ffmpeg_command)

    ffmpeg_command = ffmpeg_path + " -s " + str(cfg.width) + "x" + str(cfg.height) + " -i " +\
                        output_path + " ../send/"+ cfg.data + "/frame%d.png -y"
    os.system(ffmpeg_command)

def scan_qrcode_each(png_path, pre_send_index):
    if os.path.exists(png_path):
        image = cv2.imread(png_path)
        detector = cv2.wechat_qrcode_WeChatQRCode('detect.prototxt','detect.caffemodel', 'sr.prototxt','sr.caffemodel')
        res, _ = detector.detectAndDecode(image)
        if len(res) > 0:
            return res[0]
        else:
            return pre_send_index
    else:
        sys.exit(f"Error: {png_path} not exsist!")

def scan_qrcode_fast(recv_raw_frames_dir, received_frame_cnt):
    drop_frames_index = []
    receive_correspoding_send_index = []
    pre_send_index = 0

    for i in range(1, received_frame_cnt + 1):
        png_path = recv_raw_frames_dir + "frame" + str(i) + ".png"
        send_index = int(scan_qrcode_each(png_path, pre_send_index))
        if pre_send_index + 1 < send_index:
            drop_frames_index.extend(range(pre_send_index + 1, send_index))
        receive_correspoding_send_index.append(send_index)
        pre_send_index = send_index

    return drop_frames_index, receive_correspoding_send_index

def calc_psnr_each(i, recv_raw_frames_dir, send_raw_frames_dir, psnr_tmp_dir, receive_correspoding_send_index):
    send_index = receive_correspoding_send_index[i]
    rec_img_path = recv_raw_frames_dir + "frame" + str(i) + ".png"
    send_img_path = send_raw_frames_dir + "frame" + str(send_index) + ".png"

    send_image = cv2.imread(send_img_path)
    receive_image = cv2.imread(rec_img_path)
    mse = np.mean((send_image - receive_image) ** 2)
    if(mse == 0):  # MSE is zero means no noise is present in the signal .
                  # Therefore PSNR have no importance.
        return 100
    max_pixel = 255.0
    psnr = 20 * log10(max_pixel / sqrt(mse))

    with open(psnr_tmp_dir + str(i) + ".log", "w") as f:
        f.write(str(psnr) + "\n")

def calc_psnr_fast(recv_raw_frames_dir, send_raw_frames_dir, psnr_res_dir, received_frame_cnt, receive_correspoding_send_index):
    psnr_tmp_dir = psnr_res_dir + "tmp/"
    psnr_log_file = psnr_res_dir + "psnr.log"
    frame_psnr = []

    os.system("mkdir -p " + psnr_tmp_dir)

    pool = ThreadPoolExecutor(max_workers=20, thread_name_prefix='psnr')
    for i in range(1, received_frame_cnt + 1):
        pool.submit(calc_psnr_each, i, recv_raw_frames_dir, send_raw_frames_dir, psnr_tmp_dir, receive_correspoding_send_index)
    pool.shutdown(wait=True)

    with open(psnr_log_file, "w") as f:
        for i in range(1, received_frame_cnt + 1):
            psnr_f_str = psnr_tmp_dir + str(i) + ".log"
            if os.path.exists(psnr_f_str):
                psnr_f = open(psnr_f_str, "r")
                for psnr_line in psnr_f.readlines():
                    f.write(str(i) + "," + psnr_line)
                    frame_psnr.append(float(psnr_line))
            else:
                f.write(str(i) + "," + str(0) + "\n")
                frame_psnr.append(0)
    f.close()

    return frame_psnr

def calc_ssim_each(i, recv_raw_frames_dir, send_raw_frames_dir, ssim_tmp_dir, receive_correspoding_send_index):
    send_index = receive_correspoding_send_index[i]
    rec_img_path = recv_raw_frames_dir + "frame" + str(i) + ".png"
    send_img_path = send_raw_frames_dir + "frame" + str(send_index) + ".png"
    ssim_f_str = ssim_tmp_dir + str(i) + ".log"
    if os.path.exists(rec_img_path) and os.path.exists(send_img_path):
        ffmpeg_comand = ffmpeg_path + " -i " + rec_img_path + " -i " + send_img_path +\
            " -lavfi [0][1]ssim -f null - 2>&1| grep All | awk '{print $11}' | awk -F : '{print $2}' > " +\
            ssim_f_str
        os.system(ffmpeg_comand)

def calc_ssim_fast(recv_raw_frames_dir, send_raw_frames_dir, ssim_res_dir, received_frame_cnt, receive_correspoding_send_index):
    ssim_tmp_dir = ssim_res_dir + "tmp/"
    ssim_log_file = ssim_res_dir + "ssim.log"
    frame_ssim = []

    os.system("mkdir -p " + ssim_tmp_dir)

    pool = ThreadPoolExecutor(max_workers=20, thread_name_prefix='ssim')
    for i in range(1, received_frame_cnt + 1):
        pool.submit(calc_ssim_each, i, recv_raw_frames_dir, send_raw_frames_dir, ssim_tmp_dir, receive_correspoding_send_index)
    pool.shutdown(wait=True)

    with open(ssim_log_file, "w") as f:
        for i in range(1, received_frame_cnt + 1):
            ssim_f_str = ssim_tmp_dir + str(i) + ".log"
            if os.path.exists(ssim_f_str):
                ssim_f = open(ssim_f_str, "r")
                for ssim_line in ssim_f.readlines():
                    f.write(str(i) + "," + ssim_line)
                    frame_ssim.append(float(ssim_line))
            else:
                f.write(str(i) + "," + str(0) + "\n")
                frame_ssim.append(0)
    f.close()

    return frame_ssim

def write_data_to_file(data_lists, file):
    with open(file, 'w') as f_file:
        data_len = min([len(x) for x in data_lists])
        for i in range(data_len):
            content = ""
            for data in data_lists:
                content = content + str(data[i]) + ","
            content += "\n"
            f_file.write(content)

def read_data_from_file(file, count, data_lists, seperator):
    lines = open(file,'r').read().split('\n')
    for line in lines:
        line = line.split(seperator)
        if len(line) != count:
            continue
        for i in range(count):
            if line[i].isdigit():
                data_lists[i].append(int(line[i]))

def extract_rate_and_framesize(recv_dir):
    send_log_file = recv_dir + "send.log"
    rate_stamp_file = recv_dir + "rate_timestamp.log"
    frame_size_stamp_file = recv_dir + "frame_size_original_timestamp.log"

    os.system("rm -rf " + rate_stamp_file)
    os.system("rm -rf " + frame_size_stamp_file)

    extract_rate_command = "grep \"Send Statistics SetRates\" " + send_log_file + " | awk \'{print $13, $8}\' > " + rate_stamp_file
    extract_frame_size_command = "grep \"Send Statistics Send Frame Size\" " + send_log_file + " | awk \'{print $10, $7}\' > " + frame_size_stamp_file

    os.system(extract_rate_command)
    os.system(extract_frame_size_command)

    rate_time = []
    rate = []
    read_data_from_file(rate_stamp_file, 2, [rate_time, rate], ' ')

    frame_size_time = []
    frame_size = []
    read_data_from_file(frame_size_stamp_file, 2, [frame_size_time, frame_size], ' ')

    return rate_time, rate, frame_size_time, frame_size

def calc_delay_framesize_rate(recv_dir, res_dir):
    time_stamp_start = []
    time_stamp_end = []
    start_frame_idx = []
    end_frame_idx = []
    frame_delay = []
    frame_size = []
    end_frame_system_time_stamp = []

    recv_file = recv_dir + "recv.log"
    send_file = recv_dir + "send.log"
    start_time_stamp_file = recv_dir + "start_stamp.log"
    end_time_stamp_file = recv_dir + "end_stamp.log"
    frame_size_file = res_dir + "frame_size.log"
    delay_file = res_dir + "delay.log"
    rate_file = res_dir + "rate.log"

    os.system("rm -f " + start_time_stamp_file)
    os.system("rm -f " + end_time_stamp_file)
    os.system("rm -f " + frame_size_file)
    os.system("rm -f " + delay_file)
    os.system("rm -f " + rate_file)

    end_stamp_command = "grep \"Time Stamp\" " + recv_file + " | awk \'{print $4}\' > " + end_time_stamp_file
    start_stamp_command = "grep \"Time Stamp\" " + send_file + " | awk \'{print $4}\' > " + start_time_stamp_file
    os.system(start_stamp_command)
    os.system(end_stamp_command)

    read_data_from_file(start_time_stamp_file, 3, [[], start_frame_idx, time_stamp_start], ":")
    read_data_from_file(end_time_stamp_file, 5, [[], end_frame_idx, time_stamp_end, frame_size, end_frame_system_time_stamp], ":")

    idx = 0
    for i in range(len(time_stamp_end)):
        for j in range(idx, len(time_stamp_start)):
            if end_frame_idx[i] == start_frame_idx[j]:
                idx = j
                time_delay = time_stamp_end[i] - time_stamp_start[j]
                if time_delay > 1000:
                    print("delay too long:", i, end_frame_idx[i])
                    frame_delay.append(time_delay)
                    # exit(1)
                else:
                    frame_delay.append(time_delay)
                break

    rate_time, rate, frame_size_time, frame_size = extract_rate_and_framesize(recv_dir)
    start_time = min(rate_time[0], frame_size_time[0], end_frame_system_time_stamp[0])
    rate_time = [x - start_time for x in rate_time]
    frame_size_time = [x - start_time for x in frame_size_time]
    end_frame_system_time_stamp = [x - start_time for x in end_frame_system_time_stamp]

    write_data_to_file([range(1, len(end_frame_idx) + 1), end_frame_idx, frame_size_time, frame_size], frame_size_file)
    write_data_to_file([rate_time, rate], rate_file)
    write_data_to_file([range(1, len(end_frame_idx) + 1), end_frame_idx, end_frame_system_time_stamp, frame_delay], delay_file)

    return frame_delay

def decode_recv_video(cfg):
    re_extract_images = True
    recv_dir = "../result/" + cfg.output_dir + "/rec/" + cfg.data + "/"
    res_dir = "../result/" + cfg.output_dir + "/res/" + cfg.data + "/"

    recv_video_path = recv_dir + "recon.yuv"
    recv_raw_frames_dir = recv_dir + "raw_frames/"

    ssim_res_dir = res_dir + "ssim/"
    psnr_res_dir = res_dir + "psnr/"
    send_raw_frames_dir = "../send/" + cfg.data + "/"
    receive_correspoding_file = res_dir + "receive_correspoding_index.log"

    if re_extract_images:
        os.system("rm -rf " + recv_raw_frames_dir)
        os.system("mkdir -p " + recv_raw_frames_dir)
    os.system("rm -rf " + ssim_res_dir)
    os.system("mkdir -p " + ssim_res_dir)
    os.system("rm -rf " + psnr_res_dir)
    os.system("mkdir -p " + psnr_res_dir)

    if re_extract_images:
        # Extract all frames from recevied yuv file
        ffmpeg_command = ffmpeg_path + " -r " + str(fps) + " -s " + str(cfg.width) + "x" + str(cfg.height) + " -i " +\
                            recv_video_path + " " + recv_raw_frames_dir + "/frame%d.png -y"
        os.system(ffmpeg_command)
        received_frame_cnt = len(os.listdir(recv_raw_frames_dir))

    delay = calc_delay_framesize_rate(recv_dir, res_dir)
    drop_frames_index, receive_correspoding_send_index = scan_qrcode_fast(recv_raw_frames_dir, received_frame_cnt)
    print(f"Drop frames index: {drop_frames_index}")
    ssim = calc_ssim_fast(recv_raw_frames_dir, send_raw_frames_dir, ssim_res_dir, received_frame_cnt, receive_correspoding_send_index)
    psnr = calc_psnr_fast(recv_raw_frames_dir, send_raw_frames_dir, psnr_res_dir, received_frame_cnt, receive_correspoding_send_index)

    f_receive_correspoding = open(receive_correspoding_file, "w")
    for idx in range(len(receive_correspoding_send_index)):
        f_receive_correspoding.write(str(idx + 1) + "," + str(receive_correspoding_send_index[idx]) + "\n")
    f_receive_correspoding.close()

    return ssim, psnr, delay, drop_frames_index

def start_process(cmd, error_log_file=None):
    if error_log_file:
        with open(error_log_file, 'w') as f:
            return subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=f, stderr=f, preexec_fn=os.setsid)
    else:
        return subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, preexec_fn=os.setsid)

def kill_process(process):
    process.terminate() 
    process.wait()
    os.killpg(process.pid,signal.SIGKILL)

def send_and_recv_video(cfg):
    method_type = cfg.method_type
    loss_rate = cfg.loss_rate
    method_val = cfg.method_val
    burst_length = cfg.burst_length

    root_dir = "../../"
    res_overall_dir = "../"
    words = cfg.output_dir.split('/')
    trace_logs_file = "../file/trace_logs/" + str(words[0]) + ".log"

    client_bin = root_dir + "out/Default/peerconnection_localvideo"

    # Can custormize ip and port
    server_ip = "143.89.79.104"
    port = "8888"

    recv_dir = "../result/" + cfg.output_dir + "/rec/" + cfg.data + "/"
    recv_file = recv_dir + "recon.yuv"
    send_video_path = "../data/" + cfg.data + "_qrcode.yuv"

    server_command = root_dir + "out/Default/peerconnection_server --port " + port + " &"
    send_command = root_dir + "out/Default/peerconnection_localvideo --file " + send_video_path + \
        " --height " + str(cfg.height) + " --width " + str(cfg.width) + " --fps " + str(fps) + " --port " + port
    recv_command = client_bin + " --recon " + recv_file + " --server " + server_ip + " --port " + port + \
        " > " + recv_dir + "recv.log 2>&1 &\n"
    mahimahi_command = mahimahi_path + "mm-link " + str(trace_logs_file) + " " + str(trace_logs_file)# + mahimahi_path + "mm-loss-trace " +\
        #"downlink --trace-file=../file/loss_trace"

    send_log_file = recv_dir + "send.log"

    os.system("mkdir -p " + recv_dir)
    os.system("mkdir -p " + res_overall_dir)

    f_res_overal_file = open(res_overall_dir + "statistics.log", "a")

    server_process = start_process(server_command)
    time.sleep(1)

    # if enalbe mahimahi, need to explicit set server_ip and port
    recv_process = start_process(mahimahi_command)
    recv_process.stdin.write(recv_command.encode())
    recv_process.stdin.flush()
    time.sleep(1)

    # recv_process = start_process(recv_command)
    # time.sleep(1)

    send_process = start_process(send_command, send_log_file)
    send_process.wait()

    kill_process(recv_process)
    kill_process(server_process)

    ssim, psnr, delay, drop_frames_index = decode_recv_video(cfg)
    ssim = np.array(ssim)
    delay = np.array(delay)
    psnr = np.array(psnr)

    avg_ssim = np.mean(ssim)
    avg_delay = np.mean(delay)
    avg_psnr = np.mean(psnr)

    print(f"ssim: {avg_ssim} psnr: {avg_psnr} delay: {avg_delay}")
    f_res_overal_file.write("------------------- " + str(cfg.output_dir) + " ---------------------------" + "\n")
    f_res_overal_file.write(str(avg_ssim) + "," + str(avg_psnr) + "," + str(avg_delay) + "\n")
    f_res_overal_file.write("Drop frames count: " + str(len(drop_frames_index)) + "\n")
    f_res_overal_file.write("Drop frames index: " + str(drop_frames_index) + "\n")
    f_res_overal_file.close()

def show_experiment_fig(data_file, fig_file, x_index, y_index, label, x_label, start_index = 0):
    data = []
    data_index = []

    if not os.path.exists(data_file):
        return
    with open(data_file, "r") as f:
        for lines in f.readlines():
            line = lines.split(",")
            value = float(line[y_index])
            if value > 0:
                data_index.append(int(line[x_index]))
                data.append(float(value))

    plt.figure(figsize = (16, 8))
    plt.xlabel(x_label, fontsize = 14)
    plt.ylabel(label, fontsize = 14)
    plt.plot(data_index[start_index:], data[start_index:], label = label)
    plt.legend()
    plt.savefig(fig_file, bbox_inches = 'tight', pad_inches = 0.1)

def show_multi_y_axis_fig(files, x_indexes, y_indexes, labels, x_label, start_index, fig_file):
    if len(files) != len(x_indexes) or len(files) != len(y_indexes) or\
        len(files) != len(labels):
        print("Please pass filename, x_indexes, y_indexes and lable for both file!")
        return

    colors = ['r', 'g', 'b', 'c', 'm', 'y']
    fig, ax1 = plt.subplots(figsize=(16, 8))
    is_first_file = True

    for idx in range(len(files)):
        file = files[idx]
        if not os.path.exists(file):
            continue

        data = []
        data_index = []

        count = 1
        with open(file, "r") as f:
            for lines in f.readlines():
                line = lines.split(",")
                value = float(line[y_indexes[idx]])
                if value > 0:
                    data_index.append(int(line[x_indexes[idx]]))
                    data.append(float(value))
                    count += 1
        color = colors[idx]
        if is_first_file:
            ax1.plot(data_index[start_index:], data[start_index:], color)
            ax1.set_xlabel(x_label)
            ax1.set_ylabel(labels[idx], color=color, fontsize=14)
            ax1.tick_params(axis="y", labelcolor=color)
            is_first_file = False
        else:
            ax2 = ax1.twinx()
            ax2.spines['right'].set_position(('outward', 60 * idx))
            ax2.plot(data_index[start_index:], data[start_index:], color)
            ax2.set_ylabel(labels[idx], color=color, fontsize=14)
            ax2.tick_params(axis="y", labelcolor=color)

    plt.savefig(fig_file, bbox_inches = 'tight', pad_inches = 0.1)

def show_fig(cfg):
    fig_dir = "../result/" + cfg.output_dir + "/fig/" + cfg.data + "/"

    os.system("rm -rf " + fig_dir)
    os.system("mkdir -p " + fig_dir)

    res_dir = "../result/" + cfg.output_dir + "/res/" + cfg.data + "/"
    ssim_log_file = res_dir + "ssim/ssim.log"
    psnr_log_file = res_dir + "psnr/psnr.log"
    delay_file = res_dir + "delay.log"
    frame_size_file = res_dir + "frame_size.log"
    rate_file = res_dir + "rate.log"

    show_experiment_fig(delay_file, fig_dir + "/delay.png", 0, 3, "Delay", "frame_index")
    show_experiment_fig(frame_size_file, fig_dir + "/frame_size.png", 0, 3, "frame_size", "frame_index", 5)
    show_experiment_fig(ssim_log_file, fig_dir + "/ssim.png", 0, 1, "SSIM", "frame_size")
    show_experiment_fig(psnr_log_file, fig_dir + "/psnr.png", 0, 1, "PSNR", "frame_size")

    files = [delay_file, frame_size_file, rate_file]
    x_indexes = [2, 2, 0]
    y_indexes = [3, 3, 1]
    labels = ["Delay(ms)", "FrameSize(bytes)", "Rate(Mbps)"]
    show_multi_y_axis_fig(files, x_indexes, y_indexes, labels, "time stamp", 5, fig_dir + "/delay_frame_size_rate.png")

    files = [delay_file, frame_size_file, psnr_log_file]
    x_indexes = [0, 0, 0]
    y_indexes = [3, 3, 1]
    labels = ["Delay", "FrameSize", "PSNR"]
    show_multi_y_axis_fig(files, x_indexes, y_indexes, labels, "frame_index", 5, fig_dir + "/delay_framesize_psnr.png")

def parse_args():
	parser = argparse.ArgumentParser()
	parser.add_argument("--option", type=str)
	parser.add_argument("--data", type=str)
	parser.add_argument("--loss_rate", type=int)
	parser.add_argument("--method_val", type=int)
	parser.add_argument("--method_type", type=int)
	parser.add_argument("--burst_length", type=int)
	parser.add_argument("--width", type=int)
	parser.add_argument("--height", type=int)
	parser.add_argument("--output_dir", type=str)

	return parser.parse_args()

if __name__ == "__main__":
    cfg = parse_args()
    if cfg.option == "gen_send_video":
        overlay_qrcode_to_video(cfg)
    elif cfg.option == "decode_recv_video":
        decode_recv_video(cfg)
    elif cfg.option == "show_fig":
        show_fig(cfg)
    elif cfg.option == "send_and_recv":
        send_and_recv_video(cfg)
    else:
        print("invalid option")
