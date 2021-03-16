import os
import math
import time
import json
import subprocess

desk = './desk/'  # TODO: pass in this location
#desk = './desk-maniq/'
#desk = './desk-test/'
inbox = desk + 'inbox'
outbox = desk + 'outbox'
image_dir = 'images/'

class JobProcessor:
    def wait_get_job():
        print('looking for jobs in:', inbox)
        while True:
            job = JobProcessor.get_job()
            if job is not None:
                return job
            time.sleep(0.1)

    def get_job():
        """
        Finds the next unprocessed job from the inbox and returns as a dictionary.
        Jobs stay in the inbox until they are complete.
        """
        path = inbox
        files = []
        with os.scandir(path) as it:
            for entry in it:
                name = entry.name
                ctime = entry.stat().st_ctime
                age = math.floor(time.time() - ctime)
                files.append({ "name":  name, "age": age })

        if len(files) == 0:
            return None

        files = sorted(files, key = lambda i: -i['age'])
        file = files[0]
        filename = path + '/' + file['name']
        with open(filename) as f:
            content = f.read()
        job = json.loads(content)
        job['filename'] = filename
        return job 

    def update_job(job):
        """ 
        Sets the status or content of job.  If job is complete it moves to outbox
        """
        content = json.dumps(job, indent=4, sort_keys=True)
        #print(content)
        with open(job['filename'], 'w') as f:
            f.write(content)
        print(content)
        if 'status' in job and job['status'] == 'complete':
            print('move to outbox!')
            path = job['filename']
            base = os.path.basename(path)
            os.rename(path, outbox + '/' + base)

    def handle_psd(selfie, psd, destDir):
        print('handle_psd:', selfie, psd, destDir)
        PROG = '../restyle-processing/replaceSkin.py'
        p = subprocess.Popen(['python3', PROG,  '-II' , psd, '-MA', selfie, '--SAVE_OUTPUT', '-MR', '0', '-RES', '0.5', '-OD', destDir],
                stdout=subprocess.PIPE, stderr=None, text=True)
        s = p.communicate()[0]
        o = json.loads(s)
        path = o['outputPath']
        path = path.replace(desk, '')
        print('got:', path)
        return path

    def server(face_swapping=None):
        while True:
            print('waiting for a job')
            job = JobProcessor.wait_get_job()
            jobStart = start = time.time()

            print('got a job:', job)

            job['status'] = 'processing'
            job['swaps'] = []
            target_type = job['target_type']
            JobProcessor.update_job(job)

            src_image = job['src_image']
            desk_source_path = desk + src_image
            target_images = job['target_images']
            for i in range(len(target_images)):
                target_path = target_images[i]
                targetStart = time.time()
                desk_target_path = desk + target_path
                print('working on target', desk_target_path)
                src_path_no_ext, src_ext = os.path.splitext(desk_source_path)
                tgt_path_no_ext, tgt_ext = os.path.splitext(desk_target_path)
                output_dir = image_dir + job['id']
                desk_output_dir = desk + output_dir
                os.makedirs(desk_output_dir, 0o777, True)
                print('makedirs:', desk_output_dir)
                if tgt_ext == '.psd':
                    print('this is a PSD! we have work to do')
                    newFile = JobProcessor.handle_psd(desk_source_path, desk_target_path, desk_output_dir)
                    if 'psds' not in job: job['psds'] = []
                    job['psds'].append(target_path)
                    target_images[i] = newFile
                    tgt_ext = '.jpg'
                    JobProcessor.update_job(job)
                output_path = output_dir + f'/{os.path.basename(src_path_no_ext)}_{os.path.basename(tgt_path_no_ext)}' + tgt_ext
                desk_output_path = desk + output_path
                print(desk_source_path, desk_target_path, desk_output_path)
                face_swapping(desk_source_path, desk_target_path, desk_output_path, select_target="all")

                job['swaps'].append(output_path)
                job['status'] = 'partial'
                JobProcessor.update_job(job)
                targetEnd = time.time()
                print(f'****** hair swap took {targetEnd - targetStart}s target: {target_path}' )


            job['status'] = 'complete'
            JobProcessor.update_job(job)
            jobEnd = time.time()
            print(f'****** entire job took {jobEnd - jobStart}s src: {src_image} target: {target_type}')



if __name__ == "__main__":
    JobProcessor.server()
    """
    job = JobProcessor.wait_get_job()
    print(job)
    if not 'status' in job:
        job['status'] = 'processing'
        JobProcessor.update_job(job)
    time.sleep(1)
    job['status'] = 'partial'
    job['swaps'] = []
    JobProcessor.update_job(job)
    """
