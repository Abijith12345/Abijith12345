import boto3
import subprocess
import time
import wmi
import win32serviceutil
import datetime
import pytz
import getpass #to get the current user name


username = getpass.getuser()

def log(content):
    with open("deployment_script.log", "a") as log_file:
        time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_file.write(f"{time}  {username} - {content}\n")

#to create a token if the token was expired                  
def handle_expired_token(deployment_id):
    powershell_script_path="D:\AMG\AppPool_Scripts\EXTRA\Create_AWS_Cred.ps1"
    subprocess.run(["start", "powershell", powershell_script_path], shell=True)
    a=input("\npress enter after set the aws credential")
    main(deployment_id)

    
#function to ge the hostname using the instance id
def hostname(session, instance_id, suffix):
    ec2_client = session.client("ec2", region_name='us-east-1')
    reservations = ec2_client.describe_instances(InstanceIds=[instance_id]).get("Reservations")
    for reservation in reservations:
        for instance in reservation['Instances']:
            tags = instance.get("Tags", [])
            for tag in tags:
                if tag["Key"] == "Hostname":
                    return tag["Value"] + suffix
# powershell script to forced stop the Dsc fix for the before install failure  fix
def dsc_fix(server_name):
    try:
        powershell_command = f'invoke-command -computername {server_name} -scriptblock {{ gps wmi* | ? {{$_.modules.ModuleName -like "*DSC*"}} | stop-process -force }}'
        
        # Execute the PowerShell command using subprocess
        result = subprocess.run(['powershell', powershell_command], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        content=(f"Dsc process forced stopped on server {server_name}")
        print(content)
        log(content)
        check = True
        return check
    
    except Exception as e:
        content=(f"An error occurred: {str(e)} on {server_name}")
        print(f"{content}")
        log(content)



#To fix the code deployment service stopped
def service_check(server_name):
    try:
        c = wmi.WMI(computer=server_name)
        ServiceName = "codedeployagent"
        services = c.Win32_Service(Name=ServiceName)
        check = False
        for service in services:
            if service.State == "Stopped":
                print(f"{service.Name}, is in stopped state on server {server_name}). Attempting to start it...")
                win32serviceutil.StartService(ServiceName, machine=server_name)
                for _ in range(120):
                    time.sleep(2)
                    if (service := c.Win32_Service(Name=ServiceName)).State == "Running":
                        print("codedeployagent Service started successfully.")
                        check = True
                        break
            elif service.State == "Running":
                print(f"{service.Name}, is already running in server {server_name}")
                check = True
        return check  # Return the check variable
    except Exception as e:
        content=(f"An error occurred: {str(e)} on {server_name}")
        print(f"{content}")
        log(content)
 

#function to check the deploymnet got succedd or wait for it to get succeded"
def deployment(codedeploy_client, deployment_id,applicationName):
    deployment_status = codedeploy_client.get_deployment(deploymentId=deployment_id)['deploymentInfo']['status']
    print(f"Deployment Status: {deployment_status}")
    while True:
        if deployment_status == 'Succeeded':         
            print("Deployment succeeded!")
            content=(f"Deployment succeeded {deployment_id},({applicationName})")
            log(content)
            check=False
            break
        elif deployment_status == 'Failed':
            print("Deployment failed!")
            content=(f"Deployment  Failed {deployment_id},({applicationName})")          
            log(content)
            check=True
            break    
    return check
    
    
#function to create a deployment
def revision(codedeploy_client,deployment_id):
    print(f"\ninitiating deployment")
    
    response = codedeploy_client.get_deployment(
        deploymentId=deployment_id
    )
    deployment_info = response['deploymentInfo']
    applicationName = deployment_info['applicationName']
    deploymentGroupName = deployment_info['deploymentGroupName']
    
    # Accessing the revision information 
    revision_info = codedeploy_client.get_deployment(deploymentId=deployment_id)['deploymentInfo']['revision']
    #print(revision_info)
    revisionType = revision_info['revisionType']
    s3Location = revision_info['s3Location']
    bucket = s3Location['bucket']
    key = s3Location['key']
    bundleType= s3Location['bundleType']

    #creatig neew deployment revision
    deployment_response = codedeploy_client.create_deployment(
        applicationName=applicationName,
        deploymentGroupName=deploymentGroupName,
        revision={
            'revisionType': 'S3',
            's3Location': {
                'bucket': bucket,
                'key': key,
                'bundleType': bundleType
                
             }
         }
     )
    # Check the deployment status until it succeeds
    while True:
        deployment_status = codedeploy_client.get_deployment(deploymentId=deployment_response['deploymentId'])['deploymentInfo']['status']
        #print(f"Deployment Status: {deployment_status}")

        if deployment_status == 'Succeeded':         
            print("Deployment succeeded!")
            content=(f"Deployment revision succeeded {deployment_id},({applicationName})")
            log(content)
            break
        elif deployment_status == 'Failed':
            print("Deployment failed!")
            content=(f"Deployment revision Failed {deployment_id},({applicationName})")          
            log(content)
            break  
                    
        time.sleep(5) #to check the status every 5 seconds


def exe(deployment_id, codedeploy_client,session):
    try:
        global failed_at
        Failed_at=''
        global check
        check=''
        # Specify the AWS profile you want to use
        suffix= '.testdev.dianum.io'
    
        #to check the latest deployment of the specific deployment status to prevent redelpoyment for the succeded deployment
        response = codedeploy_client.get_deployment(
            deploymentId=deployment_id
        )
        deployment_info = response['deploymentInfo']
        applicationName = deployment_info['applicationName']
        deploymentGroupName = deployment_info['deploymentGroupName']
        response = codedeploy_client.list_deployments(applicationName=applicationName, deploymentGroupName=deploymentGroupName)
        deployments = response['deployments']
        deployment_id=deployments[0]
        response = codedeploy_client.get_deployment(deploymentId= deployment_id)
        latest_deployment = response['deploymentInfo']
        latest_deployment_status = latest_deployment['status']
        if latest_deployment_status == "Failed":                
            print(f"Appliaction Name :{applicationName}\nApplication Group :{deploymentGroupName}\n")
               # List deployment instances for the specified deployment
            list_instances_response = codedeploy_client.list_deployment_instances(
                deploymentId=deployment_id
            )
    
            # Extract the list of instance IDs
            instance_ids = list_instances_response['instancesList']
    
            # Iterate through the instance IDs and retrieve lifecycle events for each instance
            for instance_id in instance_ids:
                instance_response = codedeploy_client.get_deployment_instance(
                    deploymentId=deployment_id,
                    instanceId=instance_id
                )
    
        
            # Extract the lifecycle events for the instance
                lifecycle_events = instance_response['instanceSummary']['lifecycleEvents']
                # Print the lifecycle events for the instance
                #print(f"Instance ID: {instance_id}")
                for event in lifecycle_events:
                    event_name = event['lifecycleEventName']
                    status = event['status']
                    print(f"  Event: {event_name}, Status: {status}")
                    if status == 'Failed':
                        Failed_at= event_name
                    elif event_name == "ApplicationStop" and (status == "Failed"):
                        Failed_at= event_name
                    elif event_name == 'ValidateService' and status == "Succeeded":
                        Failed_at= 'Done'
                    elif event_name == "ApplicationStop" and status =="Unknown":
                        Failed_at='Unknown'
                        check = True
                    elif event_name == "ApplicationStop" and (status == "Skipped"):
                        Failed_at= 'Skipped'
                        
                if Failed_at == 'Done':
                    print("code deployment got Succeed")
                else:
                    print (f"\nDeployment Failed at: {Failed_at}")
    
                #to trouble shoot the error
                if Failed_at == 'BeforeInstall' :   
                    server_name = hostname(session, instance_id, suffix)
                    check = dsc_fix(server_name)
                    '''powershell_script_path="D:\\AMG\\VersionExtrator\\Version_Extract_DSC_fix.ps1"
                    subprocess.run(["start", "powershell", powershell_script_path], shell=True)
                    a=input("press enter after the version extract powershell script executed:")
                    content=(f'executed version extract script for {deployment_id}({applicationName})')
                    log(content)
                    check = True'''
               
                elif Failed_at == 'AfterInstall' :
                    server_name = hostname(session, instance_id, suffix)
                    print(f"\ninitiating iisreset on server {server_name}")
                                
                    powershell_command = f'powershell -Command "Invoke-Command -ComputerName {server_name} -ScriptBlock {{iisreset /RESTART}}"'
                    # Execute the PowerShell command using subprocess
                    result = subprocess.run(['powershell', powershell_command], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
                    print("\nIIS reset execution result", result.stdout)
                    if "successfully restarted" in str(result.stdout):
                        content=(f"iisreset successfully completed on {server_name} for {deployment_id}({applicationName})")
                        log(content)
                        check = True
                        
                    else:
                        content=(f"iisreset failed on {server_name} for {deployment_id}({applicationName})")
                        log(content)
                        
                elif Failed_at =='ApplicationStop':
                    server_name = hostname(session, instance_id, suffix)
                    check = service_check(server_name)
                    
                elif Failed_at == 'ApplicationStart':
                    server_name = hostname(session, instance_id, suffix)
                    print(f'!!! No resolution found !!!  connect to the server {server_name} check all the gateways')
                    content=(f"No resolution found for {deployment_id}({applicationName}) Failed_at:{Failed_at}")
                    log(content)       
                elif not Failed_at:
                    print("Deployment still in progress")
                    content=(f"Deployment still in progress for {deployment_id}({applicationName})")
                    log(content)
                    
                else:
                    print("no resolution found")
                    content=(f"No resolution found for {deployment_id}({applicationName}) Failed_at:{Failed_at}")
                    log(content)
                    
            if check == True:               
                revision(codedeploy_client, deployment_id)
            elif not check:
                print("cannot proceed with redeployment")
        
        elif latest_deployment_status == "InProgress": 
            print("deployment still in progress")
            list_instances_response = codedeploy_client.list_deployment_instances(
                deploymentId=deployment_id
            )
    
            # Extract the list of instance IDs
            instance_ids = list_instances_response['instancesList']
    
            # Iterate through the instance IDs and retrieve lifecycle events for each instance
            for instance_id in instance_ids:
                instance_response = codedeploy_client.get_deployment_instance(
                    deploymentId=deployment_id,
                    instanceId=instance_id
                )
    
        
            # Extract the lifecycle events for the instance
                lifecycle_events = instance_response['instanceSummary']['lifecycleEvents']
                # Print the lifecycle events for the instance
                #print(f"Instance ID: {instance_id}")
                for event in lifecycle_events:
                    event_name = event['lifecycleEventName']
                    status = event['status']
                    #print(f"  Event: {event_name}, Status: {status}")
                    if status == 'InProgress' and event_name == "BeforeInstall":
                        ist_timezone = pytz.timezone('Asia/Kolkata')
                        ist_timezone = pytz.timezone('Asia/Kolkata') 
                        end_time = datetime.datetime.now(ist_timezone)
                        start_time= event['startTime']
                        time_took =end_time-start_time
                        #print(time_took)
                        time_took = int(time_took.total_seconds() // 60)
                        #print(time_took)
                        if time_took > 3:
                            print(f"Appliaction Name :{applicationName}\nApplication Group :{deploymentGroupName}\n")
                            print("\n Deployment taking more than 3 minutes on BeforeInstall")
                            server_name = hostname(session, instance_id, suffix)
                            check = dsc_fix(server_name)
                            check= deployment(codedeploy_client, deployment_id,applicationName)
                        else:
                            #print("deployment still in progress")
                            check = False 

            if check == True:               
                revision(codedeploy_client, deployment_id)    
            
        else:
            print("deployment got succceeded")
            content =(f"Deployment aleready got succeeded for {deployment_id},{applicationName}")
            log(content)
            
        print("...........\n")
    except Exception as e:
        if "ExpiredToken" in str(e):
            print(f"The security token included in the request is expired")
            content=(f"The security token included in the request is expired")
            log(content)
            handle_expired_token(deployment_id)
        else:
            print(f"error occured:{(str(e))}")
            content=(f"{str(e)}")
            log(content)
        
            
    
    
def main(deployment_id):
    try:      

        # Create a session using the specified profile
        session = boto3.Session(profile_name=aws_profile)
        content=(f"started execution for {aws_profile}")
        log(content)
        
        # Create a CodeDeploy client using the session
        codedeploy_client = session.client('codedeploy', region_name= 'us-east-1') #creating a client session for ec2
        if deployment_id:
            exe(deployment_id,codedeploy_client,session)
        else:
            ist_timezone = pytz.timezone('Asia/Kolkata') 
            end_time = datetime.datetime.now(ist_timezone)
            start_time = end_time - datetime.timedelta(hours=2)       
            response = codedeploy_client.list_deployments(
                createTimeRange={'start': start_time, 'end': end_time}
            )

            deployments_info=[]

            for deployment_id in response['deployments']:
                deployment_info = codedeploy_client.get_deployment(deploymentId=deployment_id)
                deployment_status = deployment_info['deploymentInfo']['status']

                if deployment_status in ['Failed', 'InProgress']:
                    deployments_info.append(deployment_id)
            
            if deployments_info:
                print(deployments_info)
                #deployments_info=['d-0L6UBPQA2', 'd-E8ZM53RA2', 'd-WYZ9NDQA2', 'd-F4HYSHQA2']
                for deployment_id in deployments_info:
                    print(deployment_id)
                    exe(deployment_id,codedeploy_client,session)
            else:
                print("No deployment failures in past 2 hours")
                content=('No deployment failures in past 2 hours')
                log(content)
            time.sleep(10)
    except Exception as e:
        if "ExpiredToken" in str(e):
            print(f"The security token included in the request is expired")
            content=("The security token included in the request is expired")
            log(content)
            handle_expired_token(deployment_id)
        else:
            print(f"error occured:{(str(e))}")
            content=(f'{(str(e))}')
            log(content)
        


if __name__ == "__main__":
    print("1.QC\n2.UAT\n3.n3aUAT")
    while(True):
        env=input("enter the environment :")
        if env =='1' or env == "QC" or env == "qc":  
            aws_profile = 'wdc-gnw-dev'
            break
        elif env =='2' or env =="UAT" or env == "uat":
            aws_profile = 'wdc-gnw-uat'
            break
        elif env == '3' or env =="n3auat" or env == "N3AUAT":
            aws_profile = 'wdc-n3a-uat'
            break
               
        else:
            print("invalid selection")
 
    deployment_id = input("enter the deployment id or press enter to fix the latest deployment failures:")
    main(deployment_id)
    time.sleep(100)
