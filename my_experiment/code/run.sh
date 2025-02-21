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
fi

vbv_ratios=(0.3 0.5 1.0 1.5 2.0 3.0 10.0)
minQP=(2 10 15 20 25)
maxQP=(51 45 40 35 35)

length=${#minQP[@]}

for file in $(find ${trace_logs_dir} -maxdepth 1 -type f)
do
	for vbv_ratio in ${vbv_ratios[@]}
	do
		for ((i=0; i<length; i++))
		do
			filename=$(basename -- "$file")
			filename="${filename%.*}"
			# filename="static_1mbps"
			# # filename="10s_10to1mbps"
			# filename="10s_10to1_until_300s"

			converged=0
			times=0

			while [ $converged == 0 ]
			do
				output_dir="${filename}/x264_${vbv_ratio}_${minQP[i]}_${maxQP[i]}_${times}"
				times=$((times+1))
				echo "$output_dir"
				if [ $run_program == "all" ] || [ $run_program == "send_and_recv" ]; then
					python3 process_video_qrcode.py --option=send_and_recv --data=$video_name --minQP=${minQP[i]}\
					--maxQP=${maxQP[i]} --vbvRatio=${vbv_ratio} --height=$height --width=$width  --output_dir=${output_dir}
					converged=$?
					echo "The return value is: $converged"
					pid=$!
					wait $pid
				fi
				# send_and_recv contains decode process
				if [ $run_program == "decode_recv_video" ]; then
					python3 process_video_qrcode.py --option=decode_recv_video --data=$video_name --height=$height --width=$width  --output_dir=${output_dir}
					pid=$!
					wait $pid
				fi
				if [ $run_program == "all" ] || [ $run_program == "show_fig" ]; then
					python3 process_video_qrcode.py --option=show_fig --data=$video_name  --output_dir=${output_dir}
				fi
				exit 0
			done
			rm "../last_average_record.log"
			# exit 0
		done
	done
done