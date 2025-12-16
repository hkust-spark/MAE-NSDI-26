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
import psutil
import json

from concurrent.futures import ThreadPoolExecutor
from math import log10, sqrt

ffmpeg_path = "ffmpeg"
mahimahi_path = ""
fps = 30

## Generate qrcode and overlay to video
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

    send_pic = "../send/" + cfg.data

    if os.path.exists(send_pic):
      return

    gen_qrcode(cfg, frame_count)
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

## Decode received video
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

def write_data_to_file(data_lists, file):
    with open(file, 'w') as f_file:
        data_len = min([len(x) for x in data_lists])
        for i in range(data_len):
            content = ""
            for data in data_lists:
                content = content + str(data[i]) + ","
            content += "\n"
            f_file.write(content)

def read_data_from_file(file, count, data_lists, seperator, strict_mode = True):
    lines = open(file,'r').read().split('\n')
    for line in lines:
        line = line.split(seperator)
        if strict_mode:
            if len(line) != count:
                continue
            for i in range(count):
                if line[i].isdigit():
                    data_lists[i].append(int(line[i]))
        else:
            if len(line) < count:
                continue
            for i in range(count):
                data_lists[i].append(line[i])

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

def match_rate_with_frame_index(rate_file, frame_index_file, output_file):
    rate_time = []
    rate = []
    with open(rate_file, "r") as f:
        for lines in f.readlines():
            line = lines.split(",")
            rate_time.append(line[0])
            rate.append(line[1])

    rate_current_index = 0

    f_output = open(output_file, "w")

    with open(frame_index_file, "r") as f:
        for lines in f.readlines():
            line = lines.split(",")
            frame_index = line[0]
            time = int(line[2])

            if rate_current_index >= len(rate_time):
                f_output.write(str(frame_index) + ',' + str(rate[len(rate) - 1]) + '\n')

            for i in range(rate_current_index, len(rate_time) - 1):
                if time < int(rate_time[i + 1]):
                    rate_current_index = i
                    # print(i, frame_index, time, rate[i], rate_time[i + 1])
                    f_output.write(str(frame_index) + ',' + str(time) + ',' + str(rate[i]) + '\n')
                    break

    f_output.close()

def CalculateOverallDelay(rec_dir, res_dir):
    frame_size_file = os.path.join(rec_dir, 'frame_size_original_timestamp.log')
    end_stamp_file = os.path.join(rec_dir, 'end_stamp.log')
    start_stamp_file = os.path.join(rec_dir, 'start_stamp.log')
    overall_delay_file = os.path.join(res_dir, 'overall_delay.log')
    frame_encoded_time = []
    frame_end_index = []
    frame_end_time = []
    frame_start_index = []
    overall_delay = []

    read_data_from_file(frame_size_file, 2, [frame_encoded_time, []], ' ')
    read_data_from_file(end_stamp_file, 3, [[], frame_end_index, frame_end_time], ':')
    read_data_from_file(start_stamp_file, 3, [[], frame_start_index, []], ':')

    frame_encoded_time = [int(x) for x in frame_encoded_time]
    frame_end_index = [int(x) for x in frame_end_index]
    frame_end_time = [int(x) for x in frame_end_time]
    frame_start_index = [int(x) for x in frame_start_index]

    idx = 0
    for i in range(len(frame_end_index)):
        if i > 0 and frame_end_index[i] <= frame_end_index[i - 1]:
            continue
        for j in range(idx, len(frame_start_index)):
            if frame_end_index[i] == frame_start_index[j]:
                idx = j
                time_delay = int(frame_end_time[i]) - int(frame_encoded_time[j])
                overall_delay.append(time_delay)
                break

    write_data_to_file([range(len(overall_delay)), overall_delay], overall_delay_file)
    return overall_delay

def calc_delay_framesize_rate(recv_dir, res_dir):
    time_stamp_start = []
    time_stamp_end = []
    start_frame_idx = []
    end_frame_idx = []
    frame_delay = []
    frame_size = []

    recv_file = recv_dir + "recv.log"
    send_file = recv_dir + "send.log"
    start_time_stamp_file = recv_dir + "start_stamp.log"
    end_time_stamp_file = recv_dir + "end_stamp.log"
    frame_size_file = res_dir + "frame_size.log"
    delay_file = res_dir + "delay.log"
    rate_file = res_dir + "rate.log"
    rate_with_frame_index_file = res_dir + "rate_with_frame_index.log"

    os.system("rm -f " + start_time_stamp_file)
    os.system("rm -f " + end_time_stamp_file)
    os.system("rm -f " + frame_size_file)
    os.system("rm -f " + delay_file)
    os.system("rm -f " + rate_file)
    os.system("rm -f " + rate_with_frame_index_file)

    end_stamp_command = "grep \"Time Stamp\" " + recv_file + " | awk \'{print $4}\' > " + end_time_stamp_file
    start_stamp_command = "grep \"Time Stamp\" " + send_file + " | awk \'{print $4}\' > " + start_time_stamp_file
    os.system(start_stamp_command)
    os.system(end_stamp_command)

    read_data_from_file(start_time_stamp_file, 3, [[], start_frame_idx, time_stamp_start], ":")
    read_data_from_file(end_time_stamp_file, 3, [[], end_frame_idx, time_stamp_end], ":")

    idx = 0
    for i in range(len(time_stamp_end)):
        for j in range(idx, len(time_stamp_start)):
            if end_frame_idx[i] == start_frame_idx[j]:
                idx = j
                time_delay = time_stamp_end[i] - time_stamp_start[j]
                frame_delay.append(time_delay)
                break

    rate_time, rate, frame_size_time, frame_size = extract_rate_and_framesize(recv_dir)
    # frame size byte to kbps
    frame_size_bitrate = [(x * 8 * fps / 1000) for x in frame_size]
    start_time = min(rate_time[0], frame_size_time[0], time_stamp_end[0])
    rate_time = [x - start_time for x in rate_time]
    frame_size_time = [x - start_time for x in frame_size_time]
    time_stamp_end = [x - start_time for x in time_stamp_end]

    write_data_to_file([range(1, len(end_frame_idx) + 1), end_frame_idx, frame_size_time, frame_size, frame_size_bitrate], frame_size_file)
    write_data_to_file([rate_time, rate], rate_file)
    write_data_to_file([range(1, len(end_frame_idx) + 1), end_frame_idx, time_stamp_end, frame_delay], delay_file)

    match_rate_with_frame_index(rate_file, frame_size_file, rate_with_frame_index_file)

    overall_delay = CalculateOverallDelay(recv_dir, res_dir)

    return frame_delay, overall_delay

def calculate_send2receive_index(res_dir, send_frames_dir, receive_correspoding_send_index):
    send2receive_index_file = res_dir + '/send2receive_index.log'

    os.system("rm " + send2receive_index_file)

    send2receive_index_list = []

    f_send2receive_index_file = open(send2receive_index_file, 'w')

    send_start_index = receive_correspoding_send_index[0]
    send_frame_cnt = int(len(os.listdir(send_frames_dir)))
    receive_frame_cnt = len(receive_correspoding_send_index)
    print(send_start_index, receive_frame_cnt)

    receive2send_list_index = 0
    send_index = send_start_index
    last_receive_correspoding_send_index = -1
    while receive2send_list_index < receive_frame_cnt:
        current_receive_index = receive2send_list_index
        current_receive_correspoding_send_index = receive_correspoding_send_index[receive2send_list_index]
        # print(send_index, current_receive_correspoding_send_index, receive2send_list_index)
        while send_index < current_receive_correspoding_send_index:
            f_send2receive_index_file.write(str(send_index) + ',' + str(current_receive_index)+ '\n')
            # print(f'write {send_index},{current_receive_index}')
            send_index += 1
        if current_receive_correspoding_send_index < last_receive_correspoding_send_index:
            print(f"Reach the end of send file, {current_receive_correspoding_send_index} < {last_receive_correspoding_send_index}, {send_index}, {send_frame_cnt}")
            while send_index <= send_frame_cnt:
                f_send2receive_index_file.write(str(send_index) + ',' + str(current_receive_index)+ '\n')
                # print(f'write {send_index},{current_receive_index}')
                send_index += 1
            send_index = 1
            while send_index < current_receive_correspoding_send_index:
                f_send2receive_index_file.write(str(send_index) + ',' + str(current_receive_index)+ '\n')
                # print(f'write {send_index},{current_receive_index}')
                send_index += 1
        receive2send_list_index += 1
        last_receive_correspoding_send_index = current_receive_correspoding_send_index

    f_send2receive_index_file.close()

    return send2receive_index_list

def sync_frames(original_raw_frames_dir, rec_dir, res_dir, width, height):
    receive_raw_frames_dir = f'{rec_dir}raw_frames/'

    updated_send_file_prefix = f'{rec_dir}updated_send'
    updated_rec_file_prefix = f'{rec_dir}updated_recon'

    send2receive_index = []
    send_start_index = -1
    with open(f'{res_dir}send2receive_index.log', 'r') as f:
        for line in f.readlines():
            if send_start_index == -1:
                send_start_index = int(line.split(',')[0])
            send2receive_index.append([int(line.split(',')[0]), int(line.split(',')[1])])
    print(f"send_start_index: {send_start_index}")
    print(len(send2receive_index))

    send_frame_cnt = len(send2receive_index)
    f_output_yuv = open(f'{updated_send_file_prefix}.yuv', 'wb')
    for i in range(send_start_index + 10, len(send2receive_index)):
        send_img_path = original_raw_frames_dir + "frame" + str(send2receive_index[i][0]) + ".png"
        send_img = open(send_img_path, 'rb').read()
        # print(send_img_path)
        f_output_yuv.write(send_img)
    f_output_yuv.close()

    f_output_yuv = open(f'{updated_rec_file_prefix}.yuv', 'wb')
    for i in range(send_start_index + 10, len(send2receive_index)):
        rev_img_path = receive_raw_frames_dir + "frame" + str(send2receive_index[i][1]) + ".png"
        rev_img = open(rev_img_path, 'rb').read()
        # print(rev_img_path)
        f_output_yuv.write(rev_img)
    f_output_yuv.close()

    os.system(f'ffmpeg -s {width}x{height} -i {updated_rec_file_prefix}.yuv -c:v libx264 -preset superfast -qp 0 -y {updated_rec_file_prefix}.mp4')
    os.system(f'ffmpeg -s {width}x{height} -i {updated_send_file_prefix}.yuv -c:v libx264 -preset superfast -qp 0 -y {updated_send_file_prefix}.mp4')

def calculate_vmaf_score(rec_dir, send_filename, rec_filename):
    vmaf_command = f'docker run --rm -v {rec_dir}:/socket gfdavila/easyvmaf -r /socket/{send_filename}.mp4 -d /socket/{rec_filename}.mp4'
    os.system(vmaf_command)

def generate_head_result(data, ratio):
    data.sort()
    data_len = len(data)
    head_data = data[:int(data_len * ratio)]
    mean_head_data = np.mean(head_data)
    return mean_head_data

def read_json_file(rec_dir, vmaf_score_file, f_overall_vmaf_score):
    vmaf_score_json_file = f'{rec_dir}updated_recon_vmaf.json'
    f_vmaf_score = open(vmaf_score_file, 'w')
    vmaf_scores = []

    with open(vmaf_score_json_file, 'r') as f:
        datas = json.load(f)
        vmaf_mean = datas['pooled_metrics']['vmaf']['mean']
        vmaf_harmonic_mean = datas['pooled_metrics']['vmaf']['harmonic_mean']
        for frame in datas['frames']:
            vmaf_scores.append(float(frame['metrics']['vmaf']))
            f_vmaf_score.write(f"{frame['frameNum']},{frame['metrics']['vmaf']}\n")
        vmaf_scores = np.array(vmaf_scores)
        f_overall_vmaf_score.write(f"{vmaf_mean},{vmaf_harmonic_mean},{generate_head_result(vmaf_scores, 0.1)},{generate_head_result(vmaf_scores, 0.2)},{generate_head_result(vmaf_scores, 0.3)},{generate_head_result(vmaf_scores, 0.5)}\n")
    return vmaf_scores

def generate_vmaf_result(original_raw_frames_dir, rec_dir, res_dir, width, height, f_overall_vmaf_score):
    vmaf_score_file = f'{res_dir}vmaf_score.log'
    if os.path.exists(vmaf_score_file):
        os.remove(vmaf_score_file)

    sync_frames(original_raw_frames_dir, rec_dir, res_dir, width, height)
    calculate_vmaf_score(rec_dir, 'updated_send', 'updated_recon')

    vmaf_scores = read_json_file(rec_dir, vmaf_score_file, f_overall_vmaf_score)

    updated_send_file_prefix = f'{rec_dir}updated_send'
    updated_rec_file_prefix = f'{rec_dir}updated_recon'
    os.system(f'rm {updated_send_file_prefix}.mp4')
    os.system(f'rm {updated_rec_file_prefix}.mp4')
    os.system(f'rm {updated_send_file_prefix}.yuv')
    os.system(f'rm {updated_rec_file_prefix}.yuv')

    return vmaf_scores

def decode_recv_video(cfg):
    re_extract_images = True
    root_directory = os.path.dirname(os.getcwd()) + "/"
    recv_dir = root_directory + "result/" + cfg.output_dir + "/rec/"
    res_dir = root_directory + "result/" + cfg.output_dir + "/res/"

    os.system("mkdir -p " + res_dir)

    recv_video_path = recv_dir + "recon.yuv"
    recv_raw_frames_dir = recv_dir + "raw_frames/"

    send_raw_frames_dir = root_directory + "send/" + cfg.data + "/"
    receive_correspoding_file = res_dir + "receive_correspoding_index.log"

    if re_extract_images:
        os.system("rm -rf " + recv_raw_frames_dir)
        os.system("mkdir -p " + recv_raw_frames_dir)
        # Extract all frames from recevied yuv file
        ffmpeg_command = ffmpeg_path + " -r " + str(fps) + " -s " + str(cfg.width) + "x" + str(cfg.height) + " -i " +\
                            recv_video_path + " " + recv_raw_frames_dir + "/frame%d.png -y"
        os.system(ffmpeg_command)
    received_frame_cnt = len(os.listdir(recv_raw_frames_dir))

    delay, overall_delay = calc_delay_framesize_rate(recv_dir, res_dir)
    drop_frames_index, receive_correspoding_send_index = scan_qrcode_fast(recv_raw_frames_dir, received_frame_cnt)
    print(f"Drop frames index: {drop_frames_index}")
    print(len(drop_frames_index))

    f_receive_correspoding = open(receive_correspoding_file, "w")
    for idx in range(len(receive_correspoding_send_index)):
        f_receive_correspoding.write(str(idx + 1) + "," + str(receive_correspoding_send_index[idx]) + "\n")
    f_receive_correspoding.close()

    calculate_send2receive_index(res_dir, send_raw_frames_dir, receive_correspoding_send_index)

    f_overall_vmaf_file = open('../overall_vmaf_score.log', 'a+')
    f_overall_vmaf_file.write(f"{cfg.data},{cfg.output_dir},")
    vmaf_scores = generate_vmaf_result(send_raw_frames_dir, recv_dir, res_dir, cfg.width, cfg.height, f_overall_vmaf_file)

    os.system("rm -rf " + recv_raw_frames_dir)

    return delay, drop_frames_index, vmaf_scores, overall_delay

## Send and receive video
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

def run_receive_process(client_bin, recv_file, server_ip, port, recv_dir, trace_file):
    # if enalbe mahimahi, need to explicit set server_ip and port
    enable_mahimahi_limit = True
    enable_screenshot = False
    
    if enable_screenshot:
        recv_command = client_bin + " --gui --recon " + recv_file + " --server " + server_ip + " --port " + port + \
            " > " + recv_dir + "recv.log 2>&1 &\n"
        xvfb_display_command = "export DISPLAY=:100 && Xvfb :100 -screen 0 1280x720x24&"
        recv_process = start_process(xvfb_display_command + " && " + recv_command)
        # subprocess.run(recv_command)
        # ffmpeg_command = "ffmpeg -video_size 1280x720 -framerate 30 -f x11grab -i :100 -r 30 -y output.mp4&"
        # screenshot_process = start_process(ffmpeg_command)
    else:
        recv_command = client_bin + " --recon " + recv_file + " --server " + server_ip + " --port " + port + \
            " > " + recv_dir + "recv.log 2>&1 &\n"
        recv_process = -1

    trace_logs_file = "../file/trace_logs/" + trace_file + ".log"
    mahimahi_command = mahimahi_path + "mm-link " + str(trace_logs_file) + " " + str(trace_logs_file)# + mahimahi_path + "mm-loss-trace " +\
        #"downlink --trace-file=../file/loss_trace"

    if enable_mahimahi_limit:
        if recv_process == -1:
            recv_process = start_process(mahimahi_command)
        else:
            recv_process.stdin.write(mahimahi_command.encode())
            recv_process.stdin.flush()
            time.sleep(1)
        recv_process.stdin.write(recv_command.encode())
        recv_process.stdin.flush()
        time.sleep(1)
    else:
        if recv_process == -1:
            recv_process = start_process(recv_command)
        else:
            # subprocess.run(recv_command)
            recv_process.stdin.write(recv_command.encode())
            recv_process.stdin.flush()
        time.sleep(1)
    return recv_process


def output_tail_result(f_result_csv_file, data, ratio):
    data.sort()
    data_len = len(data)
    tail_data = data[int(data_len * (1 - ratio)):]
    mean_tail_data = np.mean(tail_data)
    f_result_csv_file.write(str(mean_tail_data))
    return mean_tail_data

def output_head_result(f_result_csv_file, data, ratio):
    data.sort()
    data_len = len(data)
    head_data = data[:int(data_len * ratio)]
    mean_head_data = np.mean(head_data)
    f_result_csv_file.write(str(mean_head_data))
    return mean_head_data

def output_statistic_result(f_res_overal_file, f_result_csv_file, delay, drop_frames_index, prefix, vmaf_scores, overall_delay):
    delay = np.array(delay)
    vmaf_scores = np.array(vmaf_scores)
    overall_delay = np.array(overall_delay)

    avg_delay = np.mean(delay)
    avg_vmaf = np.mean(vmaf_scores)
    avg_overall_delay = np.mean(overall_delay)

    f_res_overal_file.write("------------------- " + str(cfg.output_dir) + "--" + str(cfg.data) + " ---------------------------" + "\n")
    f_res_overal_file.write(str(cfg.output_dir) + "," + str(avg_delay) + "," + str(len(drop_frames_index)) + "," + str(avg_vmaf) + str(avg_overall_delay) + "\n")
    f_res_overal_file.write("Drop frames count: " + str(len(drop_frames_index)) + "\n")
    f_res_overal_file.write("Drop frames index: " + str(drop_frames_index) + "\n")
    f_res_overal_file.close()

    f_result_csv_file.write(prefix + "," + str(avg_delay) + "," + str(len(drop_frames_index)) + ',')
    avg_tail_delay = output_tail_result(f_result_csv_file, delay, 0.1)
    avg_head_vmaf = generate_head_result(vmaf_scores, 0.1)
    f_result_csv_file.write(f',{avg_vmaf},{avg_head_vmaf},{avg_overall_delay},')
    avg_tail_overall_delay = output_tail_result(f_result_csv_file, overall_delay, 0.1)
    f_result_csv_file.write("\n")
    f_result_csv_file.close()

    if not os.path.exists("../last_average_record.log"):
        f_average_record_file = open("../last_average_record.log", "w")
        f_average_record_file.write("0,0,0,0,0,0,0\n")
        f_average_record_file.close()
    datas = open("../last_average_record.log", 'r').read().split('\n')[0].split(',')
    trails_count = int(datas[0])
    last_trails_avg_delay = float(datas[1])
    last_trails_avg_tail_delay = float(datas[2])
    last_trails_avg_vmaf = float(datas[3])
    last_trails_avg_head_vmaf = float(datas[4])
    last_trails_avg_overall_delay = float(datas[5])
    last_trails_avg_tail_overall_delay = float(datas[6])

    new_trails_count = trails_count + 1
    new_trails_avg_delay = (last_trails_avg_delay * trails_count + avg_delay) / new_trails_count
    new_trails_avg_tail_delay = (last_trails_avg_tail_delay * trails_count + avg_tail_delay) / new_trails_count
    new_trails_avg_vmaf = (last_trails_avg_vmaf * trails_count + avg_vmaf) / new_trails_count
    new_trails_avg_head_vmaf = (last_trails_avg_head_vmaf * trails_count + avg_head_vmaf) / new_trails_count
    new_trails_avg_overall_delay = (last_trails_avg_overall_delay * trails_count + avg_overall_delay) / new_trails_count
    new_trails_avg_tail_overall_delay = (last_trails_avg_tail_overall_delay * trails_count + avg_tail_overall_delay) / new_trails_count

    f_average_record_file = open("../last_average_record.log", "w")
    f_average_record_file.write(str(new_trails_count) + ',' + str(new_trails_avg_delay) + ',' + str(new_trails_avg_tail_delay) + ',' + str(new_trails_avg_vmaf) + ',' + str(new_trails_avg_head_vmaf) + ',' + str(new_trails_avg_overall_delay) + ',' + str(new_trails_avg_tail_overall_delay) + '\n')

    f_average_record_file = open("../average_records.log", "a")
    f_average_record_file.write(prefix + ',' + str(new_trails_count) + ',' + str(new_trails_avg_delay) + ',' + str(new_trails_avg_tail_delay) + ',' + str(new_trails_avg_vmaf) + ',' + str(new_trails_avg_head_vmaf) + ',' + str(new_trails_avg_overall_delay) + ',' + str(new_trails_avg_tail_overall_delay) + '\n')

    converged = False
    if abs(new_trails_avg_vmaf - last_trails_avg_vmaf) < 0.5 and abs(new_trails_avg_head_vmaf - last_trails_avg_head_vmaf) < 0.5 and abs(new_trails_avg_tail_delay - last_trails_avg_tail_delay) < 0.5:
        converged = True

    return converged, new_trails_count, new_trails_avg_delay, new_trails_avg_tail_delay, new_trails_avg_vmaf, new_trails_avg_head_vmaf, new_trails_avg_overall_delay, new_trails_avg_tail_overall_delay

def send_and_recv_video(cfg):
    minQP = cfg.minQP
    maxQP = cfg.maxQP
    vbvRatio = cfg.vbvRatio
    codecMode = cfg.codecMode

    root_dir = "../../"
    res_overall_dir = "../"
    words = cfg.output_dir.split('/')

    client_bin = root_dir + "out/Default/peerconnection_localvideo"
    send_bin = root_dir + "out/Default/peerconnection_localvideo"

    # Need to custormize ip and port
    server_ip = "143.89.192.45"
    port = "8888"

    recv_dir = "../result/" + cfg.output_dir + "/rec/"
    recv_file = recv_dir + "recon.yuv"
    send_video_path = "../data/" + cfg.data + "_qrcode.yuv"

    server_command = root_dir + "out/Default/peerconnection_server --port " + port + " &"
    send_command = f"{send_bin} --file " + send_video_path + \
        " --min_qp " + str(minQP) + " --max_qp " + str(maxQP) +\
        " --vbv_buffer_ratio " + str(vbvRatio) +\
        " --codec_choose " + str(codecMode) +\
        " --height " + str(cfg.height) + " --width " + str(cfg.width) + " --fps " + str(fps) +\
        " --server " + server_ip + " --port " + port

    send_log_file = recv_dir + "send.log"

    os.system("mkdir -p " + recv_dir)
    os.system("mkdir -p " + res_overall_dir)

    f_res_overal_file = open(res_overall_dir + "every_trail_statistics.log", "a")
    f_result_csv_file = open(res_overall_dir + "every_trail_statistics.csv", "a")

    server_process = start_process(server_command)
    time.sleep(1)

    recv_process = run_receive_process(client_bin, recv_file, server_ip, port, recv_dir, str(words[1]))

    send_process = start_process(send_command, send_log_file)
    send_process.wait()

    kill_process(recv_process)
    kill_process(server_process)

    delay, drop_frames_index, vmaf_scores, overall_delay = decode_recv_video(cfg)
    prefix = str(cfg.data) + ',' + str(words[1]) + ',' + str(words[2])
    converged, count, avg_delay, avg_tail_delay, avg_vmaf, avg_head_vmaf, avg_overall_delay, avg_tail_overall_delay = output_statistic_result(f_res_overal_file, f_result_csv_file, delay, drop_frames_index, prefix, vmaf_scores, overall_delay)

    if converged:
        f_parameter_record_file = open("../parameter_result.log", "a")
        f_parameter_record_file.write(prefix + ',' + str(count) + ',' + str(avg_delay) + ',0,0,' + str(avg_tail_delay) + ',' + str(avg_vmaf) + ',' + str(avg_head_vmaf) + ',' + str(avg_overall_delay) + ',' + str(avg_tail_overall_delay) + '\n')

    return converged

## Show figure
def show_multi_plot_fig(files, x_indexes, y_indexes, labels, x_label, y_label, fig_file, start_index = 0, end_index = 10000):
    if len(files) != len(x_indexes) or len(files) != len(y_indexes):
        print("Please pass filename, x_indexes, y_indexes and lable for both file!")
        return

    colors = ['r', 'g', 'b', 'c', 'm', 'y']
    plt.figure(figsize = (16, 8))
    plt.xlabel(x_label, fontsize = 14)
    plt.ylabel(y_label, fontsize = 14)

    for idx in range(len(files)):
        file = files[idx]
        if not os.path.exists(file):
            continue

        data = []
        data_index = []

        with open(file, "r") as f:
            for lines in f.readlines():
                line = lines.split(",")
                value = float(line[y_indexes[idx]])
                if value > 0:
                    data_index.append(int(line[x_indexes[idx]]))
                    data.append(float(value))
        color = colors[idx]
        plt.plot(data_index[start_index:end_index], data[start_index:end_index], label = labels[idx], color = color)

    plt.legend()
    plt.grid()
    plt.savefig(fig_file, bbox_inches = 'tight', pad_inches = 0.1)

def show_experiment_fig(data_file, fig_file, x_index, y_index, label, x_label, start_index = 0, end_index = 10000):
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
    plt.plot(data_index[start_index:end_index], data[start_index:end_index], label = label)
    plt.legend()
    plt.grid()
    plt.savefig(fig_file, bbox_inches = 'tight', pad_inches = 0.1)

def show_fig(cfg):
    fig_dir = "../result/" + cfg.output_dir + "/fig/"
    os.system("rm -rf " + fig_dir)
    os.system("mkdir -p " + fig_dir)

    res_dir = "../result/" + cfg.output_dir + "/res/"
    vmaf_log_file = res_dir + "vmaf_score.log"
    frame_size_file = res_dir + "frame_size.log"
    rate_file_with_frame_index = res_dir + "rate_with_frame_index.log"
    overall_delay_file = res_dir + "overall_delay.log"

    show_experiment_fig(vmaf_log_file, fig_dir + "/vmaf.png", 0, 1, "VMAF", "frame_index")
    show_experiment_fig(overall_delay_file, fig_dir + "/overall_delay.png", 0, 1, "Overall Delay(ms)", "Frame Index", 5)

    files = [rate_file_with_frame_index, frame_size_file]
    x_indexes = [0, 0]
    y_indexes = [2, 4]
    labels = ["Rate", "FrameSize"]
    show_multi_plot_fig(files, x_indexes, y_indexes, labels, "frame_index", "Rate(kbps)", fig_dir + "/rate_frame_size.png", 1)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--option", type=str)
    parser.add_argument("--data", type=str)
    parser.add_argument("--minQP", type=int)
    parser.add_argument("--maxQP", type=int)
    parser.add_argument("--vbvRatio", type=float)
    parser.add_argument("--codecMode", type=int)
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--output_dir", type=str)

    return parser.parse_args()

if __name__ == "__main__":
    cfg = parse_args()
    if cfg.option == "gen_send_video":
        overlay_qrcode_to_video(cfg)
    elif cfg.option == "send_and_recv":
        converged = send_and_recv_video(cfg)
        if converged:
            sys.exit(1)
    elif cfg.option == "decode_recv_video":
        delay, drop_frames_index, vmaf_scores = decode_recv_video(cfg)
        f_res_overal_file = open("../every_trail_statistics.log", "a")
        f_result_csv_file = open("../every_trail_statistics.csv", "a")
        words = cfg.output_dir.split('/')
        prefix = str(cfg.data) + ',' + str(words[1]) + ',' + str(words[2])
        converged = output_statistic_result(f_res_overal_file, f_result_csv_file, delay, drop_frames_index, prefix, vmaf_scores)
    elif cfg.option == "show_fig":
        show_fig(cfg)
    else:
        print("invalid option")
