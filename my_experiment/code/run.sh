#!/bin/bash

burst_length=2
lr=10
method_type=2
run_loop=3

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

for method_val in 40
do
	for file in $(find ${trace_logs_dir} -maxdepth 1 -type f)
	do
		filename=$(basename -- "$file")
		filename="${filename%.*}"

		for times in $(seq $run_loop)
		do
			output_dir="${filename}/vbv_bitrate_${times}"
			echo "$output_dir"
			if [ $run_program == "gen_send_video" ]; then
				python3 process_video_qrcode.py --option=gen_send_video --data=$video_name --height=$height --width=$width
			fi
			if [ $run_program == "all" ] || [ $run_program == "send_and_recv" ]; then
				python3 process_video_qrcode.py --option=send_and_recv --data=$video_name --loss_rate=$lr\
				--method_type=$method_type --method_val=$method_val --burst_length=$burst_length --height=$height --width=$width  --output_dir=${output_dir}
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
		done
	done
done