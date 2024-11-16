import os
import qrcode
import cv2
import argparse
import matplotlib.pyplot as plt
import numpy as np
import subprocess
import signal
import time

from concurrent.futures import ThreadPoolExecutor

ffmpeg_path = "ffmpeg"
mahimahi_path = "~/install/mahimahi/bin/"
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

def scan_qrcode_each(i, qrcode_raw_dir, qrcode_res_dir, pre_res):
    png_path = qrcode_raw_dir+"/frame"+str(i)+".png"
    if os.path.exists(png_path):
        image = cv2.imread(png_path)
        detector = cv2.wechat_qrcode_WeChatQRCode('detect.prototxt','detect.caffemodel', 'sr.prototxt','sr.caffemodel')
        res, _ = detector.detectAndDecode(image)
        if len(res) != 0:
            command = "mv " + png_path + " " + qrcode_res_dir + "/frames" + str(res[0]) + ".png"
            os.system(command)
            return res[0], 0
        else:
            command = "mv " + png_path + " " + qrcode_res_dir + "/frames" + str(pre_res) + ".png"
            os.system(command)
            return pre_res, 1

def scan_qrcode_fast(frame_list, qrcode_raw_dir, qrcode_res_dir):
    frame_translation = []
    cnt = 0

    res, flag = scan_qrcode_each(frame_list[0]-1, qrcode_raw_dir, qrcode_res_dir, 1)
    pre_res = res

    for i in frame_list:
        res, flag = scan_qrcode_each(i, qrcode_raw_dir, qrcode_res_dir, pre_res)

        if flag:
            cnt += 1
            res = pre_res
        else:
            res = int(res)
        frame_translation.append(res)
    return frame_translation, cnt

def scan_qrcode(num, qrcode_raw_dir, qrcode_res_dir):
    frame_translation = []
    cnt = 0
    for i in range(1, num+1):
        if i == 1:
            pre_res = 1
        else:
            pre_res = frame_translation[-1] + 1

        res, flag = scan_qrcode_each(i, qrcode_raw_dir, qrcode_res_dir, pre_res)

        if flag:
            cnt += 1
            res = pre_res
        else:
            res = int(res)
        frame_translation.append(res)
    return frame_translation, cnt

def cal_ssim_each(i, send_image_path, ssim_tmp_dir, qrcode_res_path):
    rec_img_path = qrcode_res_path+"/frames"+str(i)+".png"
    send_img_path = send_image_path+"frame"+str(i)+".png"
    ssim_f_str = ssim_tmp_dir+str(i)+".log"

    if os.path.exists(rec_img_path):
        ffmpeg_comand = ffmpeg_path + " -i " + rec_img_path + " -i " + send_img_path +\
            " -lavfi [0][1]ssim -f null - 2>&1| grep All | awk '{print $11}' | awk -F : '{print $2}' > " +\
            ssim_f_str
        os.system(ffmpeg_comand)

        ssim_f = open(ssim_f_str, "r")
        for ssim_line in ssim_f.readlines():
            ssim_line = ssim_line.split(",")

def cal_ssim_fast(frame_list, send_image_path, ssim_res_path, qrcode_res_path):
    ssim_tmp_dir = ssim_res_path+"tmp/"
    ssim_all = ssim_res_path+"ssim.log"
    frame_ssim = []

    os.system("mkdir -p " + ssim_tmp_dir)

    pool = ThreadPoolExecutor(max_workers=20, thread_name_prefix='ssim')
    for i in frame_list:
        pool.submit(cal_ssim_each, i, send_image_path, ssim_tmp_dir, qrcode_res_path)
    pool.shutdown(wait=True)

    with open(ssim_all, "w") as f:
        for i in frame_list:
            ssim_f_str = ssim_tmp_dir + str(i) + ".log"
            if os.path.exists(ssim_f_str):
                ssim_f = open(ssim_f_str, "r")
                for ssim_line in ssim_f.readlines():
                    f.write(str(i)+","+ssim_line)
                    frame_ssim.append(float(ssim_line))
            else:
                f.write(str(i)+","+str(-1)+"\n")
                frame_ssim.append(-1)
    f.close()

    return frame_ssim

def cal_ssim(num, send_image_path, ssim_res_path, qrcode_res_path):
    ssim_tmp_dir = ssim_res_path+"tmp/"
    ssim_all = ssim_res_path+"ssim.log"
    frame_ssim = []

    os.system("mkdir -p " + ssim_tmp_dir)

    pool = ThreadPoolExecutor(max_workers=20, thread_name_prefix='ssim')
    for i in range(1, num+1):
        pool.submit(cal_ssim_each, i, send_image_path, ssim_tmp_dir, qrcode_res_path)
    pool.shutdown(wait=True)

    with open(ssim_all, "w") as f:
        for i in range(1, num+1):
            ssim_f_str = ssim_tmp_dir + str(i) + ".log"
            if os.path.exists(ssim_f_str):
                ssim_f = open(ssim_f_str, "r")
                for ssim_line in ssim_f.readlines():
                    f.write(str(i)+","+ssim_line)
                    frame_ssim.append(float(ssim_line))
            else:
                f.write(str(i)+","+str(-1)+"\n")
                frame_ssim.append(-1)
    f.close()

    return frame_ssim

def cal_delay(recv_dir):
    time_stamp_start = []
    time_stamp_end = []
    start_frame_idx = []
    end_frame_idx = []
    frame_delay = []

    bursty = 1

    recv_file = recv_dir+"recv.log"
    send_file = recv_dir+"send.log"
    start_time_stamp_file = recv_dir+"start_stamp.log"
    end_time_stamp_file = recv_dir+"end_stamp.log"
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
                time_delay = time_stamp_end[i]-time_stamp_start[j]
                if time_delay > 1000:
                    print("delay too long:", end_frame_idx[i])
                    exit(1)
                else:
                    frame_delay.append(time_stamp_end[i]-time_stamp_start[j])
                break

    if bursty:
        burst_time_stamp_file = recv_dir+"burst_stamp.log"
        burst_start_stamp_command = "grep \"pkt lost\" " + recv_file + " | awk \'{print $4}\' > " + burst_time_stamp_file
        burst_frame_idx = []
        os.system(burst_start_stamp_command)
        f = open(burst_time_stamp_file, "r")
        for line in f.readlines():
            if int(line) not in burst_frame_idx:
                burst_frame_idx.append(int(line))
        return frame_delay, burst_frame_idx
    else:
        return frame_delay, [-1]

def show_experiment_fig(cfg, fig_dir):
    our_data_path = "../res/"+cfg.data+"/x264/naive/"
    deadline_data_path = "../res/"+cfg.data+"/x264/deadline_aware/"

    loss_rate = [10]
    threshold = [40, 50, 60, 70, 80, 90, 100, 110, 120, 130]
    retrans_times = [1, 2, 3]

    our_ssim_mean_lists = []
    our_ssim_std_lists = []
    our_load_time_mean_lists = []
    our_load_time_std_lists = []
    deadline_ssim_mean_lists = []
    deadline_ssim_std_lists = []
    deadline_load_time_mean_lists = []
    deadline_load_time_std_lists = []

    for elem1 in loss_rate:
        ssim_mean_list = []
        ssim_std_list = []
        load_time_mean_list = []
        load_time_std_list = []
        for elem2 in threshold:
            with open(our_data_path+str(elem1)+"_"+str(elem2)+".log", "r") as f:
                ssim_tmp_list = []
                load_time_tmp = []
                for lines in f.readlines():
                    line = lines.split(",")
                    ssim_tmp_list.append(float(line[0]))
                    load_time_tmp.append(float(line[1]))
            ssim_mean_list.append(np.mean(ssim_tmp_list))
            load_time_mean_list.append(np.mean(load_time_tmp))
            ssim_std_list.append(np.std(ssim_tmp_list))
            load_time_std_list.append(np.std(load_time_tmp))
            f.close()
        our_ssim_mean_lists.append(ssim_mean_list)
        our_ssim_std_lists.append(ssim_std_list)
        our_load_time_mean_lists.append(load_time_mean_list)
        our_load_time_std_lists.append(load_time_std_list)

    for elem1 in loss_rate:
        ssim_mean_list = []
        ssim_std_list = []
        load_time_mean_list = []
        load_time_std_list = []
        for elem2 in retrans_times:
            with open(deadline_data_path+str(elem1)+"_"+str(elem2)+".log", "r") as f:
                ssim_tmp_list = []
                load_time_tmp = []
                for lines in f.readlines():
                    line = lines.split(",")
                    ssim_tmp_list.append(float(line[0]))
                    load_time_tmp.append(float(line[1]))
            ssim_mean_list.append(np.mean(ssim_tmp_list))
            load_time_mean_list.append(np.mean(load_time_tmp))
            ssim_std_list.append(np.std(ssim_tmp_list))
            load_time_std_list.append(np.std(load_time_tmp))
            f.close()
        deadline_ssim_mean_lists.append(ssim_mean_list)
        deadline_ssim_std_lists.append(ssim_std_list)
        deadline_load_time_mean_lists.append(load_time_mean_list)
        deadline_load_time_std_lists.append(load_time_std_list)

    plt.figure(dpi=300, figsize=(7, 4.2))
    plt.xlabel("SSIM loss", fontsize=12)
    plt.ylabel("Load time", fontsize=12)
    ax = plt.gca()
    for i in range(len(our_ssim_mean_lists)):
        plt.plot(our_ssim_mean_lists[i], our_load_time_mean_lists[i], '-o', label=str(loss_rate[i])+"% loss rate (our)")

    for i in range(len(deadline_ssim_mean_lists)):
        plt.plot(deadline_ssim_mean_lists[i], deadline_load_time_mean_lists[i], '-o', label=str(loss_rate[i])+"% loss rate (deadline)")

    for i in range(len(our_load_time_mean_lists)):
        for j in range(len(our_load_time_mean_lists[i])):
            ax.annotate(str(threshold[j]), xy=(our_ssim_mean_lists[i][j], our_load_time_mean_lists[i][j]))

    for i in range(len(deadline_load_time_mean_lists)):
        for j in range(len(deadline_load_time_mean_lists[i])):
            ax.annotate(str(retrans_times[j]), xy=(deadline_ssim_mean_lists[i][j], deadline_load_time_mean_lists[i][j]))

    plt.legend()
    plt.savefig(fig_dir+"experiment_dot_plot.png", bbox_inches='tight', pad_inches=0.1)

    plt.figure(dpi=300, figsize=(7, 4.2))
    plt.xlabel("SSIM loss", fontsize=12)
    plt.ylabel("Load time", fontsize=12)
    ax = plt.gca()
    for i in range(len(our_ssim_std_lists)):
        plt.errorbar(our_ssim_mean_lists[i], our_load_time_mean_lists[i], yerr=0.5*np.
                     array(our_load_time_std_lists[i]), fmt='o', label=str(loss_rate[0])+"% loss rate (our)")

    for i in range(len(deadline_ssim_std_lists)):
        plt.errorbar(deadline_ssim_mean_lists[i], deadline_load_time_mean_lists[i], yerr=0.5*np.
                     array(deadline_load_time_std_lists[i]), fmt='o', label=str(loss_rate[0])+"% loss rate (deadline)")
        
    for i in range(len(our_load_time_mean_lists)):
        for j in range(len(our_load_time_mean_lists[i])):
            ax.annotate(str(threshold[j]), xy=(our_ssim_mean_lists[i][j], our_load_time_mean_lists[i][j]))

    for i in range(len(deadline_load_time_mean_lists)):
        for j in range(len(deadline_load_time_mean_lists[i])):
            ax.annotate(str(retrans_times[j]), xy=(deadline_ssim_mean_lists[i][j], deadline_load_time_mean_lists[i][j]))

    plt.legend()
    plt.savefig(fig_dir+"experiment_error_plot.png", bbox_inches='tight', pad_inches=0.1)

def show_fig(cfg):
    fig_dir = "../fig/"+cfg.data+"/"

    show_experiment_fig(cfg, fig_dir)

def overlay_qrcode_to_video(cfg, num):
    gen_qrcode(cfg, num)

    send_pic = "../send/" + cfg.data

    os.system("rm -rf "+send_pic)
    os.system("mkdir -p "+send_pic)

    video_path = "../data/"+cfg.data+".yuv"
    qrcode_path = "../qrcode/"+cfg.data+"/qrcode_output.yuv"
    output_path = "../data/"+cfg.data+"_qrcode.yuv"
    ffmpeg_command = ffmpeg_path + " -s 1920x1080 -i " +\
                        video_path + " -s 138x138 -i " +\
                        qrcode_path + " -s 138x138 -i " +\
                        qrcode_path + " -s 138x138 -i " +\
                        qrcode_path + " -filter_complex \"[0][1]overlay=30:30[v1]; " +\
                                        "[v1][2]overlay=960:30[v2]; " +\
                                        "[v2][3]overlay=1700:30[v3]\" -map \"[v3]\" " +\
                        output_path + " -y"
    print(ffmpeg_command)
    os.system(ffmpeg_command)

    ffmpeg_command = ffmpeg_path + " -s 1920x1080 -i " +\
                        output_path + " ../send/"+ cfg.data + "/frame%d.png -y"
    os.system(ffmpeg_command)

def decode_recv_video(cfg, num):
    recv_dir = "../rec/"+cfg.data+"/"

    video_path = recv_dir+"recon.yuv"
    qrcode_dir_path = recv_dir+"raw_frames"
    qrcode_res_path = recv_dir+"res_frames"

    ssim_res_path = "../res/"+cfg.data+"/ssim/"
    send_image_path = "../send/"+cfg.data+"/"
    delay_file = ssim_res_path+"delay.log"

    os.system("rm -rf "+qrcode_dir_path)
    os.system("rm -rf "+qrcode_res_path)
    os.system("mkdir -p "+qrcode_dir_path)
    os.system("mkdir -p "+qrcode_res_path)

    ffmpeg_command = ffmpeg_path + " -r " + str(fps) + " -s 1920x1080 -i " +\
                        video_path + " " + qrcode_dir_path + "/frame%d.png -y"

    os.system(ffmpeg_command)
    os.system("rm -rf "+ssim_res_path)
    os.system("mkdir -p "+ssim_res_path)

    delay, burst_frame_idx = cal_delay(recv_dir)
    frame_translation, warning_cnt = scan_qrcode_fast(burst_frame_idx, qrcode_dir_path, qrcode_res_path)
    ssim = cal_ssim_fast(frame_translation, send_image_path, ssim_res_path, qrcode_res_path)
    # frame_translation, warning_cnt = scan_qrcode(num, qrcode_dir_path, qrcode_res_path)
    # ssim = cal_ssim(num, send_image_path, ssim_res_path, qrcode_res_path)

    f_delay = open(delay_file, "w")
    for elem in delay:
        f_delay.write(str(elem)+"\n")
    f_delay.close()

    return ssim, delay, burst_frame_idx, frame_translation, warning_cnt

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

def send_and_recv_video(cfg, num):
    method_type = cfg.method_type
    loss_rate = cfg.loss_rate
    method_val = cfg.method_val
    burst_length = cfg.burst_length

    algorithm_name = ["0", "deadline_aware", "naive"]
    
    root_dir = "../../"
    res_overall_path = "../res/"+cfg.data+"/x264/"+algorithm_name[method_type]+"/"
    res_path = "../res/"+cfg.data+"/"

    client_bin = root_dir + "out/Default/peerconnection_localvideo"
    server_ip = "100.64.0.1"
    port = "8888"

    recv_dir = "../rec/"+cfg.data+"/"
    recv_file = recv_dir + "recon.yuv"
    param_file_path = "../file/"
    send_video_path = "../data/"+cfg.data+"_qrcode.yuv"

    server_command = root_dir + "out/Default/peerconnection_server --port " + port + " &"
    send_command = root_dir + "out/Default/peerconnection_localvideo --file " + send_video_path+ \
        " --height 1080 --width 1920 --fps 30 --port " + port
    recv_command = client_bin + " --recon " + recv_file + " --server " + server_ip + " --port " + port + \
        " --method_val " + str(method_val) + " --method_type " + str(method_type) + " > " + recv_dir + "recv.log 2>&1 &\n"
    mahimahi_command = mahimahi_path + "mm-delay 7 " + mahimahi_path + "mm-loss-trace " +\
        "downlink --trace-file=../file/loss_trace"

    send_log_file = recv_dir+"send.log"
    server_file = param_file_path + "start_server"
    warning_file = "../file/warning.log"

    os.system("mkdir -p " + recv_dir)
    os.system("mkdir -p " + res_overall_path)
    os.system("mkdir -p " + res_path)

    warning_file_f = open(warning_file, "a")
    f = open(res_overall_path+str(loss_rate)+"_"+str(method_val)+".log", "a")
    server_file_f = open(server_file, "w")
    server_file_f.close()

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

    whole_ssim = []
    whole_delay = []

    ssim, delay, burst_frame_idx, frame_translation, warning_cnt = decode_recv_video(cfg, num)
    ssim = 1-np.array(ssim)
    delay = np.array(delay)

    if len(burst_frame_idx) == 0:
        warning_file_f.write("burst_frame_idx is empty, frame skip: " + str(warning_cnt) +\
                             " " + str(method_val) + " " + str(method_type) + "\n")
        warning_file_f.close()
        os.system("rm -f " + server_file)
        return

    if burst_frame_idx[0] == -1:
        warning_file_f.write("burst_frame_idx is -1, frame skip: " + str(warning_cnt) +\
                             " " + str(method_val) + " " + str(method_type) + "\n")
        warning_file_f.close()
        os.system("rm -f " + server_file)
        return

    frame_translation = np.array(frame_translation)
    ssim = np.array(ssim)
    delay = np.array(delay)
    # burst_frame_idx = np.array(burst_frame_idx[:burst_frame_idx_len])
    # ssim_idx = frame_translation[burst_frame_idx]

    if warning_cnt > 0:
        warning_file_f.write("frame skip: " + str(warning_cnt) +\
                             " " + str(method_val) + " " + str(method_type) + "\n")
        for i in range(len(frame_translation)):
            warning_file_f.write(str(frame_translation[i])+","+str(ssim[i])+"\n")
        warning_file_f.close()

    ssim = np.mean(ssim)
    burst_delay = np.mean(delay[burst_frame_idx])
    # ssim = np.mean(ssim[ssim_idx])

    whole_ssim.append(ssim)
    whole_delay.append(burst_delay)
    
    f.write(str(ssim)+","+str(burst_delay)+","+str(burst_frame_idx)+","+str(frame_translation)+"\n")
    f.close()
    os.system("rm -f " + server_file)

def parse_args():
	parser = argparse.ArgumentParser()
	parser.add_argument("--option", type=str)
	parser.add_argument("--data", type=str)
	parser.add_argument("--loss_rate", type=int)
	parser.add_argument("--method_val", type=int)
	parser.add_argument("--method_type", type=int)
	parser.add_argument("--burst_length", type=int)

	return parser.parse_args()

if __name__ == "__main__":
    num = 100
    cfg = parse_args()
    if cfg.option == "gen_send_video":
        overlay_qrcode_to_video(cfg, num)
    elif cfg.option == "decode_recv_video":
        decode_recv_video(cfg, num)
    elif cfg.option == "show_fig":
        show_fig(cfg)
    elif cfg.option == "send_and_recv":
        send_and_recv_video(cfg, num)
    else:
        print("invalid option")
