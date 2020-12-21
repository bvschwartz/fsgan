import os
import math
import time
import json

inbox = './inbox'
outbox = './outbox'
swapbox = 'data/swaps'

class JobProcessor:
    def wait_get_job():
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
        print(content)
        with open(job['filename'], 'w') as f:
            f.write(content)
        print(content)
        if 'status' in job and job['status'] == 'complete':
            print('move to outbox!')
            path = job['filename']
            base = os.path.basename(path)
            os.rename(path, outbox + '/' + base)

    def server(face_swapping=None):
        while True:
            print('waiting for a job')
            job = JobProcessor.wait_get_job()
            print('got a job:', job)

            job['status'] = 'processing'
            job['swaps'] = []
            JobProcessor.update_job(job)

            source_path = job['src_image']
            target_images = job['target_images']
            for target_path in target_images:
                print('working on target', target_path)
                src_path_no_ext, src_ext = os.path.splitext(source_path)
                tgt_path_no_ext, tgt_ext = os.path.splitext(target_path)
                output_path = swapbox + f'/{os.path.basename(src_path_no_ext)}_{os.path.basename(tgt_path_no_ext)}' + '.jpg'
                print(source_path, target_path, output_path)
                face_swapping(source_path, target_path, output_path)

                job['swaps'].append(output_path)
                job['status'] = 'partial'
                JobProcessor.update_job(job)

            job['status'] = 'complete'
            JobProcessor.update_job(job)



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
