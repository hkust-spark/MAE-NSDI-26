#!/bin/bash

burst_length=2
lr=10

method_type=2
for method_val in 40 50 60 70 80 90 100 110 120 130
do
	for times in {1..10}
	do
		python process_video_qrcode.py --option=send_and_recv --data=video_0a86 --loss_rate=$lr\
			--method_type=$method_type --method_val=$method_val --burst_length=$burst_length
		pid=$!
		wait $pid
	done
done

method_type=1
for method_val in {1..3}
do
	for times in {1..10}
	do
		python process_video_qrcode.py --option=send_and_recv --data=video_0a86 --loss_rate=$lr\
			--method_type=$method_type --method_val=$method_val --burst_length=$burst_length
		pid=$!
		wait $pid
	done
done
