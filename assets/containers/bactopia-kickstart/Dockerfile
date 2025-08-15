FROM amazoncorretto:21.0.8

# Install Nextflow
RUN curl -s https://get.nextflow.io | bash
RUN chmod +x nextflow
RUN mv nextflow /usr/local/bin

# Install dependencies
RUN yum install -y git python-pip curl jq
RUN pip install --upgrade awscli

# Install entrypoint script
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Create temp volume
VOLUME ["/scratch"]

# Set up default command
CMD ["/usr/local/bin/entrypoint.sh"]
