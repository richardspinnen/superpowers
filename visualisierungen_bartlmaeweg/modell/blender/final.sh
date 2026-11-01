#!/bin/bash
cd /home/user/bwork
for v in street garden front aerial dusk; do
  timeout 5400 /home/user/bvenv/bin/python render.py $v 2400 1600 64 /home/user/bwork/final_$v.png 1.0 2>&1 | grep "^render\|Error\|Traceback" 
done
echo ALLDONE
