import ssl
import socket
import os
import OpenSSL.crypto
from datetime import datetime
from prettytable import PrettyTable
import time
from urllib.parse import urlparse
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date
import requests
from urllib3.util.ssl_ import create_urllib3_context

#to send a notification by the teams utility box
def teams(body):
    try:
        # Webhook URL for the connector
        connector_uri = 'https://notified.webhook.office.com/webhookb2/a2c592bf-97d8-4d06-ad1c-7b84f7641adb@f6156a01-7c5b-4c82-b9ba-5750c109536e/IncomingWebhook/a13417213f1d4ba494c4bae51de714ac/a799a145-7bfe-45ac-9da6-db947514cc17'

        # Set the security protocol for the request
        create_urllib3_context().set_ciphers('HIGH:!DH:!aNULL')

        # Invoke the REST method to send the message
        response = requests.post(connector_uri, json=body)
    except Exception as e:
        print(f"can't establish a connection to teams:{str(e)}")


#function to write start time of the script
def log_start_time():
    with open("script_log.txt", "a") as log_file:
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        log_file.write(f"Script started at {current_time}\n")

#function to wrie the end time of the script
def log_end_time():
    with open("script_log.txt", "a") as log_file:
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        log_file.write(f"Script ended at {current_time}\n")


def send_email(email_to, email_subject, html_email_body, cc=None):
    # Generate the HTML table content
    table_html = table.get_html_string()
  
    # Email settings
    email_from = "Notified-AMG@Notified.com"
    #email_to = email_to
    #email_subject = email_subject
    # Create the plain text email content
    #html_email_body = html_email_body
   
    
    # Create an email message
    message = MIMEMultipart()
    message['From'] = email_from
    message['To'] = email_to
    message['Subject'] = email_subject
    if cc:
        message['Cc']=cc
    message.attach(MIMEText(html_email_body, 'html'))

    # SMTP settings
    smtp_server = "email-smtp.us-east-1.amazonaws.com"
    smtp_port = 587
    smtp_username = "AKIARMVARTHEWC2DDL4G"
    smtp_password = "BHA+AJ1wTIZJXF5gNuPfkwfZNPJ5qlNWzqzuNIvobqk4"

    # Send the email
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(smtp_username, smtp_password)
        recipients = email_to.split(', ')
        if cc:
            recipients += cc.split(', ')
        server.sendmail(email_from, recipients, message.as_string())

def get_certificate_info(url):
    try:
        check = urlparse(url)
        if check.port is None:
            port = 443
            url1 = url
        else:
            url1 = check.hostname
            port =  check.port
            
        cert = ssl.get_server_certificate((url1, port))
        x509 = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, cert)
        exp_date = datetime.strptime(x509.get_notAfter().decode('utf-8')[:8], '%Y%m%d')
        curr_date = datetime.now()
        remaining_days = (exp_date - curr_date).days
        #issue_date = datetime.strptime(x509.get_notBefore().decode('utf-8')[:8], '%Y%m%d')
        subject = dict(x509.get_subject().get_components())
        common_name = subject.get(b'CN', 'Error').decode('utf-8')
        issuer = str(x509.get_issuer().get_components())
        issuer = (issuer.split("CN")[1]).replace(", OU","").replace("', b'","").replace("')]","")

        return {'URL': url1,'CNAME': common_name,'Issuer' : issuer, 'Expiration Date': exp_date.strftime('%Y-%m-%d'), 'Remaining Days': remaining_days}
    except:
        return {'URL': url,'CNAME': 'Error','Issuer' : 'N\A','Expiration': 'N/A', 'Remaining Days': -1}

def get_certificate_info_dict(urls):
    return {url: get_certificate_info(url) for url in urls}

if __name__ == "__main__":
    os.chdir("D:\AMG\SSL_Certificate")

    '''to sent a notification to the teams chat
    body = {
        "text": f"{datetime.now()} SSL certificates check script has started executing"
    }
    teams(body)'''


    log_start_time()
    days=20 
    current_date = date.today()

    filename = 'all.txt'  
    with open(filename, 'r') as file:
        urls = [line.strip().lower() for line in file]

    certificate_info_dict = get_certificate_info_dict(urls)
    
    # Sort the dictionary by remaining days
    sorted_certificate_info_dict = dict(sorted(certificate_info_dict.items(), key=lambda item: item[1]['Remaining Days']))

    # Create a PrettyTable
    table1 = PrettyTable(sorted_certificate_info_dict[next(iter(sorted_certificate_info_dict))].keys())
    for info in sorted_certificate_info_dict.values():
        table1.add_row(info.values())

    table1.align = "l"  # Left align columns
    table1.border = True
    #print(table1)

    # Save the table to a text file
    text_file = 'certificate_info.txt'
    with open(text_file, 'w') as txt_file:
        txt_file.write(str(table1))

    #filtered by remaining days
    filtered_certificate_info_dict = {url: info for url, info in sorted_certificate_info_dict.items() if info['Remaining Days'] <= days}  #and info['CNAME'] != 'Error'
    try:
        table = PrettyTable(filtered_certificate_info_dict[next(iter(filtered_certificate_info_dict))].keys())
        for info in filtered_certificate_info_dict.values():
            email_to = "ferdine.silva@notified.com"
            email_subject = f"Expiring Certificate Alert - {current_date.strftime('%d/%m/%y')}"
            table.add_row(info.values())
            table_html = table.get_html_string()
            html_email_body = f"""
            <html>
            <body>Hi Team,<br><br>Please find the Expiring certificate details within {days} days.<br><br>
                {table_html}
            </body>
            </html>
            """
            cc="abijith.h@notified.com"
            
        send_email(email_to, email_subject, html_email_body,cc)
    except StopIteration:
        print(f"No certificates with remaining days less than {days} found.")


    #filtered by remaining days
    filtered_certificate_info_dict = {url: info for url, info in sorted_certificate_info_dict.items() if info['Remaining Days'] == days  and info['CNAME'] != 'Error'}
    try:
        table = PrettyTable(filtered_certificate_info_dict[next(iter(filtered_certificate_info_dict))].keys())
        for info in filtered_certificate_info_dict.values():
            email_to = "amgsupport-cw@notified.com"
            cc= "abijith.h@notified.com"
            email_subject = f"{info['URL']} Certificate Expiration Notification - {current_date.strftime('%d/%m/%y')}"
            table.add_row(info.values())
            # Generate the HTML table content
            table_html = table.get_html_string()
            html_email_body = f"""
            <html>
            <body>Hi Team,<br><br>Please find the certificate details of {info['URL']}  expire within {info['Remaining Days']} days.<br><br>
                {table_html}
            </body>
            </html>
            """

            send_email(email_to,email_subject, html_email_body,cc)
            table.clear_rows()
    except StopIteration:
        print(f"No certificates with expiring date {days} found.")

    
    
    #conditions for sending a notification to the teams
    filtered_certificate_info_dict = {url: info for url, info in sorted_certificate_info_dict.items() if info['Remaining Days'] <= days  and info['CNAME'] != 'Error'}
    if not filtered_certificate_info_dict:
        # Constructing the message body
        body = {
            "text": f"{datetime.now()} SSL certificates check script executed, no certificates are set to expire within the next {days} days "
        }
        
        teams(body)
    else:
        keys_of_first_item = list(filtered_certificate_info_dict.values())[0].keys()

        # Find the number of columns
        num_columns = len(keys_of_first_item)
        body = {
            "text": f"{datetime.now()} SSL certificates check script executed, {num_columns} certificates are set to expire within the next {days} days "
        }
        teams(body)

    
    
    log_end_time()
    
