# MAE
Welcome! This repo is a WebRTC-based More Adaptive Encoder (MAE) proposed in the paper "MAE: More Adaptive Video Encoder for Consistent Low Latency in High-Quality Real-Time Communication" (to appear). We are working on a more stable version but please do let us know if you encounter any issues.

**WebRTC is a free, open software project** that provides browsers and mobile
applications with Real-Time Communications (RTC) capabilities via simple APIs.
The WebRTC components have been optimized to best serve this purpose.

## Before You Start

First, be sure to install the [depot_tools](https://www.chromium.org/developers/how-tos/install-depot-tools/).
```
git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git
export PATH=/path/to/depot_tools:$PATH
```

Then, install [x264](https://code.videolan.org/videolan/x264).

```
git clone https://code.videolan.org/videolan/x264
./configure --enable-shared  --enable-static
make
make install
```

## Getting the Code

For desktop development:

Clone the current repo:

```
git clone https://github.com/hkust-spark/MAE-NSDI-26.git
```

Enter the root directory of the repo:

```
cd ./MAE-NSDI-26
git submodule update --init --recursive
```
**We also provide a Docker image for easy environment deployment; for details, see the [Docker](#docker) section at the end of this README.**

Sync with other WebRTC-related repos using the `gclient` tool installed before.

```
gclient sync
```

NOTICE: During your first sync, you’ll have to accept the license agreement of the Google Play Services SDK.

The checkout size is large due the use of the Chromium build toolchain and many dependencies. 

## Generating Ninja project files

[Ninja](https://ninja-build.org/) is the default build system for all platforms.
[Ninja](https://ninja-build.org/) project files are generated using [GN](https://gn.googlesource.com/gn/+/master/README.md). They're put in a directory of your choice, like `out/Debug`, but you can use any directory for keeping multiple configurations handy.

To generate project files using the defaults (Debug build), run (in the root directory of the repo):

```
gn gen out/Default
```

See the [GN](https://gn.googlesource.com/gn/+/master/README.md) documentation for all available options. 

## Compiling

When you have Ninja project files generated (see previous section), compile using:

For Ninja project files generated in out/Default:

```
ninja -C out/Default
```


# Experimenting Testbed Setup Guide

## Preparations

Download and install `mahimahi` and `ffmpeg`.

```bash
sudo apt-get install -y ffmpeg
```

```bash
git clone https://github.com/LW945/mahimahi.git
cd mahimahi
./configure
make
make install
```

Install cv2

```bash
pip install opencv-python 
pip install opencv-contrib-python
```

## One-tap Experiments Usage

Using `MAE-NSDI-26/my_experiment/code/run.sh` can run the whole experiment at once to make the process easier.

**Important: Configure IP Address**

Before running experiments, you must update the server IP address in the code to match your machine's public IP address:

1. Open `my_experiment/code/process_video_qrcode.py`
2. Find the `send_and_recv()` function (around line 600)
3. Update the `server_ip` variable to your machine's public IP address:
   ```python
   server_ip = "YOUR_PUBLIC_IP_ADDRESS"  # Change this to your machine's public IP
   port = "8888"  # Port can be changed if needed
   ```

**Usage**

```bash
cd my_experiment/code/
./run.sh -i Lecture -p all

# The detailed usage is:
# ./run.sh [-i <video_name>] [-p <program_name>] [-s <{width}x{height}]
```
**Input**

The script provides following inputs:

•	<video_name>: prefix of input yuv file

•	<program_name>: the program will be run, including all(run all following programs), gen_send_video, send_and_recv, decode_recv_video and show_fig"

•	<size>: (optional) custormize input file width and height, default is 1920x1080

## Detailed Usage

The process_video_qrcode.py can be run with different options to perform various tasks. The options are:

1. gen_send_video: Generate video with QR codes.
2. send_and_recv: Send video and receive it, then process the results.
3. decode_recv_video: Decode received video and calculate metrics.
4. show_fig: Generate figures from experiment results.

### **Input Video**

The video to be sent should be placed in the `my_experiment/data` directory. And the video should be in `.yuv` format.

MAE already provides an lossless compressed version of test sequence `Lecture.mp4`, the script will automaticlly uncompressed as `Lecture.yuv` file for MAE to use.


## Output Structure

After running experiments, the results are organized in the following structure:

### Directory Structure

The experiment results are stored in `my_experiment/result/` with the following hierarchy:

```
result/
└── <data_name>/                    # e.g., Lecture, Lecture_concat, Game_shoot_concat
    └── <trace_name>/               # e.g., 15s_10to2_until_300s
        └── <solution_trial>/       # e.g., MAE_salsify_0, MAE_x264_ori_1, MAE_x264_adap_2
            ├── fig/                # Generated figures (PNG files)
            │   ├── vmaf.png
            │   ├── rate_frame_size.png
            │   └── overall_delay.png
            ├── rec/                # Received video and recording logs
            │   ├── recon.yuv       # Reconstructed video
            │   ├── recv.log
            │   ├── send.log
            │   └── ...
            └── res/                # Result logs and metrics
                ├── vmaf_score.log
                ├── overall_delay.log
                └── ...
```

### Summary Files

At the top level of `my_experiment/`, the following summary files are generated:

- **`every_trail_statistics.csv`**: CSV file containing statistics from all trials, including:
  - Data name, trace name, solution name
  - Average VMAF scores
  - Average tail overall delay
  - Other performance metrics

- **`parameter_result.log`**: Log file containing detailed parameter results for each solution, including:
  - Average VMAF per solution
  - Average tail overall delay per solution
  - Number of trials per solution

- **`MAE_result.png`**: Final result figure showing VMAF vs. Tail Overall Delay comparison across all solutions, with:
  - Different markers for each solution (Salsify and WebRTC+x264 as empty circles, MAE as red star)
  - Arrow indicating the "better" direction (toward higher VMAF and lower delay)

## Docker

A Docker image is provided with all dependencies (depot_tools, x264, mahimahi, ffmpeg, Python/OpenCV) so you can avoid manual environment setup.

### 1. Build the image

From the repo root:

```bash
docker build -t mae-nsdi-26-env .
```

### 2. Configure before running experiments

Edit `my_experiment/code/process_video_qrcode.py` (in the `send_and_recv()` function, around line 600) and set:

- **`root_directory_for_vmaf_docker`**: Absolute path to this repo on the host (e.g. `"/Users/you/MAE-NSDI-26"` or `"/home/you/MAE-NSDI-26"`). Replace the placeholder `"ABSOLUTE_PATH_TO_THIS_REPO"` with your path.

### 3. Run the container

From the repo root on the host.

**On Linux host** (so user `mae` can write under `/workspace` and ownership is restored on exit):

```bash
docker run -it --rm --privileged --platform linux/amd64 \
  -v "$(pwd)":/workspace \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e HOST_WORKSPACE="$(pwd)" \
  -e HOST_IS_LINUX=1 \
  --group-add $(stat -c '%g' /var/run/docker.sock 2>/dev/null || echo 999) \
  mae-nsdi-26-env
```

**On macOS host** (omit `-e HOST_IS_LINUX=1` so the script does not change ownership of the bind-mounted repo):

```bash
docker run -it --rm --privileged --platform linux/amd64 \
  -v "$(pwd)":/workspace \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e HOST_WORKSPACE="$(pwd)" \
  --group-add $(stat -c '%g' /var/run/docker.sock 2>/dev/null || echo 999) \
  mae-nsdi-26-env
```

### 4. Inside the container

Run the preparation script first (it sets up the environment, compiles and switches to the working directory). Then run the full experiment:

```bash
./prepare.sh

# Enter 'mae' user shell
cd /workspace/my_experiment/code/

# password is 'mae'
./run.sh -i Lecture -p all
```

### Some common issues
1. ERROR: permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock
   ```bash
   newgrp docker
   docker ps # test if succeed
   ```
2. Receiver cannot connect to server

   mahimahi might change container's ip address. So first `docker run` the image, then
   ```bash
   mm-delay 10
   ip addr
   # copy the public ip of mahimahi container to `process_video_qrcode.py`
   # then exit and rerun the docker
   ```
