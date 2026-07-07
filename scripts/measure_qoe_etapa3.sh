#!/bin/bash

OUTDIR="$1"

mkdir -p "$OUTDIR"

curl -s -o "$OUTDIR/chunk_h2.m4s" \
-w "tempo=%{time_total}\ntamanho=%{size_download}\nvelocidade=%{speed_download}\nhttp=%{http_code}\n" \
http://10.0.0.1:8000/chunk-stream0-00001.m4s \
> "$OUTDIR/qoe_chunk.txt"

