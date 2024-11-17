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

def scan_qrcode_each(png_path):
    if os.path.exists(png_path):
        image = cv2.imread(png_path)
        detector = cv2.wechat_qrcode_WeChatQRCode('detect.prototxt','detect.caffemodel', 'sr.prototxt','sr.caffemodel')
        res, _ = detector.detectAndDecode(image)
        return res[0]
    else:
        sys.exit(f"Error: {png_path} not exsist!")

def scan_qrcode_fast(recv_raw_frames_dir, received_frame_cnt):
    drop_frames_index = []
    receive_correspoding_send_index = []
    pre_send_index = 0

    for i in range(1, received_frame_cnt + 1):
        png_path = recv_raw_frames_dir + "frame" + str(i) + ".png"
        send_index = int(scan_qrcode_each(png_path))
        if pre_send_index + 1 != send_index:
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

def calc_delay(recv_dir):
    time_stamp_start = []
    time_stamp_end = []
    start_frame_idx = []
    end_frame_idx = []
    frame_delay = []

    recv_file = recv_dir + "recv.log"
    send_file = recv_dir + "send.log"
    start_time_stamp_file = recv_dir + "start_stamp.log"
    end_time_stamp_file = recv_dir + "end_stamp.log"
    os.system("rm -f " + start_time_stamp_file)
    os.system("rm -f " + end_time_stamp_file)

    end_stamp_command = "grep \"Time Stamp\" " + recv_file + " | awk \'{print $4 $5 $6}\' > " + end_time_stamp_file
    start_stamp_command = "grep \"Time Stamp\" " + send_file + " | awk \'{print $4 $5 $6}\' > " + start_time_stamp_file
    os.system(start_stamp_command)
    os.system(end_stamp_command)

    f = open(start_time_stamp_file, "r")
    for line in f.readlines():
        line = line.split(":")
        if len(line) != 3:
            continue
        start_frame_idx.append(int(line[1]))
        time_stamp_start.append(int(line[2]))
    f.close()

    f = open(end_time_stamp_file, "r")
    for line in f.readlines():
        line = line.split(":")
        if len(line) != 3:
            continue
        end_frame_idx.append(int(line[1]))
        time_stamp_end.append(int(line[2]))
    f.close()

    idx = 0

    for i in range(len(time_stamp_end)):
        for j in range(idx, len(time_stamp_start)):
            if end_frame_idx[i] == start_frame_idx[j]:
                idx = j
                time_delay = time_stamp_end[i] - time_stamp_start[j]
                if time_delay > 1000:
                    print("delay too long:", end_frame_idx[i])
                    exit(1)
                else:
                    frame_delay.append(time_delay)
                break

    return frame_delay, start_frame_idx

def decode_recv_video(cfg):
    re_extract_images = True
    recv_dir = "../rec/" + cfg.data + "/"

    recv_video_path = recv_dir + "recon.yuv"
    recv_raw_frames_dir = recv_dir + "raw_frames/"

    ssim_res_dir = "../res/" + cfg.data + "/ssim/"
    psnr_res_dir = "../res/" + cfg.data + "/psnr/"
    send_raw_frames_dir = "../send/" + cfg.data + "/"
    delay_file = "../res/" + cfg.data + "/delay.log"

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

    delay, start_frame_idx = calc_delay(recv_dir)
    drop_frames_index, receive_correspoding_send_index = scan_qrcode_fast(recv_raw_frames_dir, received_frame_cnt)
    print(f"Drop frames index: {drop_frames_index}")
    ssim = calc_ssim_fast(recv_raw_frames_dir, send_raw_frames_dir, ssim_res_dir, received_frame_cnt, receive_correspoding_send_index)
    psnr = calc_psnr_fast(recv_raw_frames_dir, send_raw_frames_dir, psnr_res_dir, received_frame_cnt, receive_correspoding_send_index)

    f_delay = open(delay_file, "w")
    idx = 0
    for elem in delay:
        frame_sequence = start_frame_idx[idx]
        f_delay.write(str(idx + 1) + "," + str(frame_sequence) + "," + str(elem) + "\n")
        idx += 1
    f_delay.close()

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
    res_overall_dir = "../res/" + cfg.data + "/"

    client_bin = root_dir + "out/Default/peerconnection_localvideo"

    # Can custormize ip and port
    # server_ip = "100.64.0.1"
    # port = "8888"

    recv_dir = "../rec/" + cfg.data + "/"
    recv_file = recv_dir + "recon.yuv"
    send_video_path = "../data/" + cfg.data + "_qrcode.yuv"

    server_command = root_dir + "out/Default/peerconnection_server &"
    send_command = root_dir + "out/Default/peerconnection_localvideo --file " + send_video_path+ \
        " --height " + str(cfg.height) + " --width " + str(cfg.width) + " --fps " + str(fps)
    recv_command = client_bin + " --recon " + recv_file + " > " + recv_dir + "recv.log 2>&1 &\n"
        #" --method_val " + str(method_val) + " --method_type " + str(method_type) # + " > " + recv_dir + "recv.log 2>&1 &\n"
    mahimahi_command = mahimahi_path + "mm-delay 7 "# + mahimahi_path + "mm-loss-trace " +\
        #"downlink --trace-file=../file/loss_trace"

    send_log_file = recv_dir + "send.log"

    os.system("mkdir -p " + recv_dir)
    os.system("mkdir -p " + res_overall_dir)

    f_res_overal_file = open(res_overall_dir + "statistics.log", "a")

    server_process = start_process(server_command)
    time.sleep(1)

    recv_process = start_process(mahimahi_command)

    recv_process.stdin.write(recv_command.encode())
    recv_process.stdin.flush()
    time.sleep(1)

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
    f_res_overal_file.write(str(avg_ssim) + "," + str(avg_psnr) + "," + str(avg_delay) + "\n")
    f_res_overal_file.write("Drop frames index: " + str(drop_frames_index) + "\n")
    f_res_overal_file.close()

def show_experiment_fig(data_file, fig_file, choose_index, label):
    data = []
    data_index = []

    if not os.path.exists(data_file):
        return

    with open(data_file, "r") as f:
        for lines in f.readlines():
            line = lines.split(",")
            value = float(line[choose_index])
            if value > 0:
                data_index.append(int(line[0]))
                data.append(float(value))

    plt.figure(dpi = 300, figsize = (7, 4.2))
    plt.xlabel("frame index", fontsize = 12)
    plt.ylabel(label, fontsize = 12)
    plt.plot(data_index, data, label = label)
    plt.legend()
    plt.show()
    plt.savefig(fig_file, bbox_inches = 'tight', pad_inches = 0.1)

def show_fig(cfg):
    fig_dir = "../fig/" + cfg.data + "/"

    os.system("rm -rf " + fig_dir)
    os.system("mkdir -p " + fig_dir)

    res_dir = "../res/" + cfg.data + "/"
    ssim_log_file = res_dir + "ssim/ssim.log"
    psnr_log_file = res_dir + "psnr/psnr.log"
    delay_file = res_dir + "delay.log"

    show_experiment_fig(delay_file, fig_dir + "/delay.png", 2, "Delay")
    show_experiment_fig(ssim_log_file, fig_dir + "/ssim.png", 1, "SSIM")
    show_experiment_fig(psnr_log_file, fig_dir + "/psnr.png", 1, "PSNR")

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
