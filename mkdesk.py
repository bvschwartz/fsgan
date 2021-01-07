import os
import json


def create_desk():
    if os.path.exists(desk_path):
        print('desk already exists... remove please!')
        exit()

    os.mkdir(desk_path)
    os.mkdir(desk_path + '/inbox')
    os.mkdir(desk_path + '/outbox')
    os.mkdir(desk_path + '/www')
    os.symlink('../../TARGET_PICS_122028', desk_path + '/TARGET_PICS_122028')
    os.symlink('../../TARGET_SKINTONES_122029', desk_path + '/TARGET_SKINTONES_122029')
    os.symlink('../../SOURCE_PICS', desk_path + '/SOURCE_PICS')

def get_desk_pics(path):
    pics = []
    with os.scandir(f'{desk_path}/{path}') as it:
        for file in it:
            filename = file.name
            ext = os.path.splitext(filename)[1]
            #print('ext:', ext)
            if ext == '.jpg':
                #print(filename)
                pics.append(f'{path}/{filename}')
    return pics


def create_inbox_items(sources, targets, id_postfix=""):
    print('sources:', sources)
    for src in sources:
        print('src:', src)
        src_path_no_ext, src_ext = os.path.splitext(src)
        src_id = os.path.basename(src_path_no_ext)
        entry_path = f'{desk_path}/inbox/{src_id}.json'
        id = f'{src_id}{id_postfix}'
        #print(src, tgt)
        o = {
            "id": id,
            "status": "new",
            "src_image": src,
            "target_images": targets,
        }
        content = json.dumps(o, indent=4, sort_keys=False)
        print(content)
        #print(entry_path)
        with open(entry_path, 'w') as f: f.write(content)

html_head = '<!DOCTYPE html>\n<html lang="en">\n  <body>\n'
html_tail = '  </body>\n</html>\n'
def create_html(sources, targets):
    if not os.path.exists(desk_path + '/www'): os.mkdir(desk_path + '/www')
    html_top = html_head
    html_top += f'    <h1>Sources</h1>\n'
    for src in sources:
        print('src:', src)

        src_path_no_ext, src_ext = os.path.splitext(src)
        src_id = os.path.basename(src_path_no_ext)
        src_base = os.path.basename(src_path_no_ext)
        html_top += f'    <a href="www/{src_base}.html"><img src="{src}" height="250"></a>\n'

        html_src = html_head + f'    <img src="../{src}" height="250">\n'

        html_src += '    <h3>Target Images</h3>\n'
        for tgt in targets:
            print('   tgt:', tgt)
            html_src += f'    <img src="../{tgt}" height="250"></a>\n'
        html_src += '    <h3>Swapped Images</h3>\n'
        for tgt in targets:
            print('   tgt:', tgt)
            tgt_base = os.path.basename(tgt)
            html_src += f'    <img src="../images/{src_base}/{src_base}_{tgt_base}" height="250"></a>\n'

        html_src += html_tail
        print(html_src)
        with open(f'{desk_path}/www/{src_base}.html', 'w') as f: f.write(html_src)

    html_top += html_tail
    print(html_top)
    with open(f'{desk_path}/index.html', 'w') as f: f.write(html_top)





#create_desk()
desk_path = 'desk'
desk_path = 'desk-4x9'
desk_path = 'desk-4x6-skintone'

sources = get_desk_pics(f'SOURCE_PICS')

#targets = get_desk_pics(f'TARGET_PICS_122028')
targets = get_desk_pics(f'TARGET_SKINTONES_122029')

print(sources, targets)
#create_inbox_items(sources, targets)

create_html(sources, targets)
