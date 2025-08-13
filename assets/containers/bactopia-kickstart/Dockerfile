FROM amazoncorretto:21

# Install Nextflow
RUN curl -s https://get.nextflow.io | bash
RUN chmod +x nextflow
RUN mv nextflow /usr/local/bin

RUN yum install -y git python-pip curl jq
RUN pip install --upgrade awscli
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
VOLUME ["/scratch"]
CMD ["/usr/local/bin/entrypoint.sh"]
