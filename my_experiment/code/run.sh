#!/bin/bash
width=1920
height=1080

usage() {
	echo "[Usage] $0 [-i <video_name>] [-p <program_name>]" 1>&2;
	# echo "[Usage] The optional programs contain: all(run all following programs), "
	# echo "[Usage]                                gen_send_video, send_and_recv"
	# echo "[Usage]                                decode_recv_video and show_fig"
	# echo "[Usage] The default size is 1920x1080, can modified by [-s <{width}x{height}]"
	# echo "[Usage] For example: $0 -i video_0a86 -p all -o test_output -s 1920x1080"
	exit 1;
}

while getopts ":i:p:s:" opt; do
    case "${opt}" in
        i)
            video_name=${OPTARG}
            ;;
        p)
            p=${OPTARG}
			if [ $p == "all" ] || [ $p == "send_and_recv" ] || [ $p == "gen_send_video" ] ||
			   [ $p == "decode_recv_video" ] || [ $p == "show_fig" ]; then
				run_program=${p}
			else
				usage
			fi
            ;;
		s)
			s=${OPTARG}
			s=(${s//x/ })
			width=${s[0]}
			height=${s[1]}
			;;
        *)
            usage
            ;;
    esac
done
shift $((OPTIND-1))

if [ -z "${video_name}" ] || [ -z "${run_program}" ]; then
    usage
fi

trace_logs_dir="../file/trace_logs"

if [ $run_program == "gen_send_video" ]; then
	python3 process_video_qrcode.py --option=gen_send_video --data=$video_name --height=$height --width=$width
	exit 0
fi

vbv_ratios=(0.04 0.1 0.3 0.5)
minQP=(2)
maxQP=(63)
# at least run 10 times
repeat_time=10

SendAndDecode() {
	# parameter list: 1.output_dir 2.vbv_ratio 3.video_name 4.minQP 5.maxQP 6.height 7.width
	python3 process_video_qrcode.py --option=send_and_recv --data=$3 --minQP=$4\
	--maxQP=$5 --vbvRatio=$2\
	--height=$6 --width=$7  --output_dir=$1
	converged=$?
	pid=$!
	wait $pid
	return $converged
}

for file in $(find ${trace_logs_dir} -maxdepth 1 -type f)
do
	for vbv_ratio in ${vbv_ratios[@]}
	do
		filename=$(basename -- "$file")
		filename="${filename%.*}"
		# filename="static_1mbps"
		# filename="15s_10to1_until_300s"
		# vbv_ratio=0.3

		converged=0
		times=0

		if [ $run_program == "all" ] || [ $run_program == "send_and_recv" ]; then
			# general send process
			while [ $converged == 0 ] || [ $times -lt $repeat_time ]
			do
				output_dir="${video_name}/${filename}/x264_${vbv_ratio}_${times}"
				echo $output_dir
				SendAndDecode ${output_dir} ${vbv_ratio} ${video_name} ${minQP[0]} ${maxQP[0]} ${height} ${width}
				# break
				converged=$?
				times=$((times+1))
				echo "The return value is: $converged"

				res_dir="../result/${output_dir}/res/"
				rm -rf "${res_dir}/psnr/tmp"
				rm -rf "${res_dir}/psnr_consider_drop/tmp"
				rec_dir="../result/${output_dir}/rec/"
				ffmpeg -s ${width}x${height} -i ${rec_dir}/recon.yuv -c:v libx264 -preset superfast -qp 0 -y ${rec_dir}/recon.mp4
				rm "${rec_dir}/recon.yuv"
				python3 process_video_qrcode.py --option=show_fig --data=$video_name  --output_dir=${output_dir}
				# exit 0
			done
			if [ -e "../last_average_record.log" ]; then
				rm "../last_average_record.log"
			fi
			if [ -e "../last_average_record_drop_period.log" ]; then
				rm "../last_average_record_drop_period.log"
			fi
		fi
		# send_and_recv contains decode process
		if [ $run_program == "decode_recv_video" ]; then
			output_dir="${video_name}/${filename}/x264_${vbv_ratio}_0"
			python3 process_video_qrcode.py --option=decode_recv_video --data=$video_name --height=$height --width=$width  --output_dir=${output_dir}
			pid=$!
			wait $pid
			exit 0
		fi
		if [ $run_program == "all" ] || [ $run_program == "show_fig" ]; then
			output_dir="${video_name}/${filename}/x264_${vbv_ratio}_0"
			python3 process_video_qrcode.py --option=show_fig --data=$video_name  --output_dir=${output_dir}
		fi
	done # vbv_ratios
	# exit 0
done # trace logs
