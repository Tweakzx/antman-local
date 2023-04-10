FROM nvidia/cuda:11.0-base

WORKDIR /workspace

RUN sed -i 's/archive.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list

RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-keys A4B469963BF863CC 

RUN apt-get update --allow-unauthenticated && apt-get install -y python3 python3-pip

ADD ./requriments.txt .

ADD ./local_coordinator.py .

RUN pip install -r requriments.txt

CMD sh