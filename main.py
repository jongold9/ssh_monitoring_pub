import os
import paramiko
import smtplib
from email.mime.text import MIMEText
import time
import socket

smtp_server = "smtp.gmail.com"
smtp_port = 587
email_user = "example1@gmail.com"
email_password = "hPAShc232422"
recipient_email = "example2@gmail.com"
email_subject_prefix = "Warning"

servers = [
    {
        "name": "ex1",
        "hostname": "10.10.10.1",
        "port": 22,
        "username": "master_15656",
        "ssh_key_path": "/root/.ssh/id_rsa"
    },
    {
        "name": "ex2",
        "hostname": "10.10.10.2",
        "port": 22,
        "username": "master_15656",
        "ssh_key_path": "/root/.ssh/id_rsa"
    },
]

def send_email(subject, message):
    msg = MIMEText(message)
    msg['Subject'] = subject
    msg['From'] = email_user
    msg['To'] = recipient_email

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(email_user, email_password)
            server.sendmail(email_user, recipient_email, msg.as_string())
    except Exception:
        pass  # Email sending failed

def get_cpu_usage(client):
    stdin, stdout, stderr = client.exec_command(
        "top -bn1 | grep 'Cpu(s)'"
    )
    cpu_output = stdout.read().decode().strip()

    if 'id,' in cpu_output:
        parts = cpu_output.split(',')
        idle_part = next((part for part in parts if 'id' in part), None)
        if idle_part:
            idle_cpu = float(idle_part.split()[0])
            cpu_usage = 100 - idle_cpu
            return cpu_usage

    raise ValueError("Unexpected format of top output")

def get_average_cpu_usage(client, duration=30):
    total_cpu = 0
    iterations = duration

    for _ in range(iterations):
        try:
            cpu_usage = get_cpu_usage(client)
            total_cpu += cpu_usage
        except Exception:
            pass
        time.sleep(1)

    return total_cpu / iterations

def get_server_stats(client):
    # Get memory stats
    stdin, stdout, stderr = client.exec_command(
        "vmstat -s | grep -E 'total memory|used memory'"
    )
    vmstat_output = stdout.read().decode().strip().split("\n")
    
    total_memory = int(vmstat_output[0].split()[0])
    used_memory = int(vmstat_output[1].split()[0])
    
    memory_usage = (used_memory / total_memory) * 100

    # Get CPU stats (averaged over 30 seconds)
    cpu_usage = get_average_cpu_usage(client, duration=30)

    # Get load average
    stdin, stdout, stderr = client.exec_command(
        "uptime | awk -F'[a-z]:' '{ print $2 }'"
    )
    load_average = stdout.read().decode().strip()

    # Get disk stats
    stdin, stdout, stderr = client.exec_command(
        "df / | tail -1 | awk '{print $5}'"
    )
    disk_usage = int(stdout.read().decode().strip().replace('%', ''))

    return memory_usage, cpu_usage, load_average, disk_usage

def check_and_report(client, server):
    try:
        memory_usage, cpu_usage, load_average, disk_usage = get_server_stats(client)

        if memory_usage > 80 or cpu_usage > 80 or disk_usage > 90:
            subject = f"{email_subject_prefix}: High resource usage on server {server['name']}"
            message = (
                f"Server: {server['name']} ({server['hostname']})\n"
                f"CPU usage (Total): {cpu_usage:.2f}%\n"
                f"Memory usage: {memory_usage:.2f}%\n"
                f"Disk usage: {disk_usage}%\n"
                f"Load average: {load_average}"
            )
            send_email(subject, message)
    except Exception as e:
        error_message = f"An error occurred on server {server['name']} ({server['hostname']}): {e}"
        send_email(f"Error on server {server['name']}", error_message)

def check_server(server):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ip_address = socket.gethostbyname(server['hostname'])
        client.connect(ip_address, server['port'], server['username'], key_filename=server['ssh_key_path'])
        check_and_report(client, server)
    except Exception:
        pass
    finally:
        client.close()

def main():
    for server in servers:
        check_server(server)

if __name__ == "__main__":
    main()
