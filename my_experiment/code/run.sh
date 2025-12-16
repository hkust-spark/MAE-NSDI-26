#!/bin/bash
width=1920
height=1080

usage() {
	echo "[Usage] $0 [-i <video_name>] [-p <program_name>]" 1>&2;
	echo "[Usage] The optional programs contain: all(run all following programs), "
	echo "[Usage]                                gen_send_video, send_and_recv"
	echo "[Usage]                                decode_recv_video and show_fig"
	echo "[Usage] The default size is 1920x1080, can modified by [-s <{width}x{height}]"
	echo "[Usage] For example: $0 -i video_0a86 -p all -o test_output -s 1920x1080"
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

if [ $run_program == "gen_send_video" ] || [ $run_program == "all" ]; then
	python3 process_video_qrcode.py --option=gen_send_video --data=$video_name --height=$height --width=$width
  if [ $run_program == "gen_send_video" ]; then # only generate qrcode for input video
	  exit 0
  fi
fi

codec_modes_name=("x264_ori" "salsify" "x264_adap")
codec_modes=(2 3 4) # (0: vp8), (1: av1) (2: x264 original) (3: Salsify) (4: x264 adaptive) (5: CBR)
# at least run 3 times
repeat_time=3
maxrepeat_time=3

SendAndDecode() {
	# parameter list: 1.output_dir 2.vbv_ratio 3.video_name 4.minQP 5.maxQP 6.height 7.width 8.codec_mode
	python3 process_video_qrcode.py --option=send_and_recv --data=$3 --minQP=$4\
	--maxQP=$5 --vbvRatio=$2 --codecMode=$8\
	--height=$6 --width=$7  --output_dir=$1
	converged=$?
	pid=$!
	wait $pid
	return $converged
}

for file in $(find ${trace_logs_dir} -maxdepth 1 -type f)
do
	for i in ${!codec_modes[@]}
	do
		filename=$(basename -- "$file")
		filename="${filename%.*}"

		codec_mode=${codec_modes[$i]}
		codec_mode_name=${codec_modes_name[$i]}

		converged=0
		times=0

    vbv_ratio=0.5
    minQP=2
    maxQP=60

		if [ $run_program == "all" ] || [ $run_program == "send_and_recv" ]; then
			# general send process
			while [ $converged == 0 ] || [ $times -lt $repeat_time ]
			do
				output_dir="${video_name}/${filename}/MAE_${codec_mode_name}_${times}"
				echo $output_dir

				SendAndDecode ${output_dir} ${vbv_ratio} ${video_name} ${minQP} ${maxQP} ${height} ${width} ${codec_mode}
				converged=$?
				times=$((times+1))
				echo "The return value is: $converged"

        python3 process_video_qrcode.py --option=show_fig --data=$video_name  --output_dir=${output_dir}

				if [ $times -ge $maxrepeat_time ]; then
					echo "Reach the max repeat time: $maxrepeat_time"
					break
				fi
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
			output_dir="${video_name}/${filename}/${codec_mode_name}_${times}"
			python3 process_video_qrcode.py --option=decode_recv_video --data=$video_name --height=$height --width=$width  --output_dir=${output_dir}
			pid=$!
			wait $pid
			exit 0
		fi
		if [ $run_program == "show_fig" ]; then
			output_dir="${video_name}/${filename}/MAE_${codec_mode_name}_${times}"
			python3 process_video_qrcode.py --option=show_fig --data=$video_name  --output_dir=${output_dir}
		fi
	done # codec modes
done # trace logs

if [ $run_program == "all" ]; then
	python3 GenerateFinalResullt.py --data=$video_name
fi