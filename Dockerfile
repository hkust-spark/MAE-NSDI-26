# MAE-NSDI-26 artifact evaluation environment
FROM --platform=linux/amd64 ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    sudo \
    build-essential \
    git \
    curl \
    python3 \
    python3-pip \
    ca-certificates \
    ssl-cert \
    libxcb1-dev \
    libxcb-present-dev \
    libcairo2-dev \
    libpango1.0-dev \
    protobuf-compiler \
    libprotobuf-dev \
    # x264
    nasm \
    # mahimahi build deps (configure checks for apache2)
    autoconf \
    automake \
    libtool \
    pkg-config \
    libssl-dev \
    iptables \
    iproute2 \
    apache2 \
    apache2-dev \
    dnsmasq \
    # experiment testbed
    ffmpeg \
    iputils-ping \
    ufw \
    # peerconnection_localvideo and other GUI examples
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# Docker CLI so VMAF can run via host socket
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "${VERSION_CODENAME:-$VERSION_ID}") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && apt-get update && apt-get install -y --no-install-recommends docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git /opt/depot_tools \
    && ln -s /opt/depot_tools/ninja /opt/depot_tools/ninja-linux 2>/dev/null || true
# Bootstrap depot_tools once (creates python3_bin_reldir.txt etc.) so gn/gclient work
RUN env DEPOT_TOOLS_UPDATE=1 /opt/depot_tools/update_depot_tools
ENV DEPOT_TOOLS_UPDATE=0
ENV PATH="/opt/depot_tools:${PATH}"

RUN git clone https://code.videolan.org/videolan/x264 /tmp/x264 \
    && cd /tmp/x264 \
    && ./configure --enable-shared --enable-static --prefix=/usr \
    && make -j$(nproc) \
    && make install \
    && cd / \
    && rm -rf /tmp/x264

RUN git clone https://github.com/LW945/mahimahi.git /tmp/mahimahi \
    && cd /tmp/mahimahi \
    && ./autogen.sh \
    && ./configure \
    && make -j$(nproc) \
    && make install \
    && ldconfig \
    && cd / \
    && rm -rf /tmp/mahimahi

RUN pip3 install --no-cache-dir \
    opencv-python \
    opencv-contrib-python \
    qrcode \
    matplotlib \
    psutil

WORKDIR /workspace

# Start PulseAudio in the background so WebRTC audio device init succeeds (avoid send.log errors)
CMD ["sh", "-c", "pulseaudio -D --exit-idle-time=-1 2>/dev/null || true; exec /bin/bash"]