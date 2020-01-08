import os
import sys
npos = os.getcwd().rfind('/')
add_path = os.getcwd()[0:npos]
sys.path.append(add_path)

import base64
import json
import random
import requests
import shutil
import time

import cv2
import numpy as np
import zmq
from flask import Flask, abort, jsonify, request, Response
from munch import Munch


import ray
import socket
import threading
import traceback

import pyarrow.plasma as plasma
from flask_restful import Api
from multiprocessing import Process,Lock
from flask_restful import Resource,request
from Media_Brain_Resource_Manage.Media_Brain_Resource_Manage_Client_Log import *
from Media_Brain_Resource_Manage.Media_Brain_Resource_Api import Resource_Rest_Api
from Media_Brain_Resource_Manage.Resoure_Model_Work.Resource_Manage_Client_Register import *
from Media_Brain_Resource_Manage import Media_Brain_Resource_Manage_Mutual_Info as Code
from Media_Brain_Resource_Manage.Resoure_Model_Work.Resource_Manage_Client_Model_Manage import ModelMange,modelManager
from Media_Brain_Resource_Manage.Resoure_Model_Work.Resource_Manage_System_Res_Info import SystemResourceInfo

mutex = Lock()



def net_is_used(port,ip='127.0.0.1'):

    s = socket.socket(socket.AF_INET,socket.SOCK_STREAM)

    try:

        s.connect((ip,port))
        s.shutdown(2)
        print('%s:%d is unused' % (ip,port))
        return False

    except:

        print('%s:%d is used' % (ip,port))
        return True


def Random_Port():

    import random

    while(True):

        port = ""
        for i in range(4):

            ch = chr(random.randrange(ord('1'), ord('9') + 1))
            port += ch

        if net_is_used(int(port)):
            return port


def set_task_communicate_address(strUrl,ip,name):

    msg = {}
    msg['server_address'] = strUrl
    msg['local_IP'] = ip
    msg['share_pyarr'] = name
    msg['share_memory'] = 2000000000
    with open('/tmp/Sobey_Resource_info.json',"w") as f:
        json.dump(msg, f)

    return True


def init_model(resourcelist, localIp, share_name):

    OnWriteLog("init_model start")
    Resource_Info = []
    thread_pool = []
    # 检查当前系统资源
    sys_resource = SystemResourceInfo()

    try:

        for re in resourcelist:
            if int(re.get('number')) <= 0:
                continue
            gpu_info = sys_resource.get_gpu_info()

            if re.get('model_name') == Code.MODEL_FACE:
                print("start init FACE model ")
                from Media_Brain_Resource_Manage.Resoure_Model_Work.FACE_Model_Work.work_pro import face_model_work
                reg_re = {}
                reg_re['model_name'] = Code.MODEL_FACE
                reg_re['number'] = 0
                reg_re['model_memory'] = re.get('single_model_memory')
                reg_re['run_memory'] = re.get('run_memory')
                for index in range(int(re.get('number'))):
                    print("get the sys_resource")
                    gpu_info = sys_resource.get_gpu_info()
                    print("get the sys_resource end")
                    for gpu in gpu_info:
                        if gpu.get('GPU_Free') >= reg_re['model_memory'] + reg_re['run_memory']:
                            print("start the FACE model process")
                            model = modelManager()
                            face_modelmanage = model.ModelMange(Model_Name=Code.MODEL_FACE, Proce_Model='actual', IP=localIp)
                            ret = Process(target=face_model_work,args=(face_modelmanage,int(gpu.get('GPU_Serial_Number')), mutex, share_name))

                            ret.start()
                            thread_pool.append(ret)
                            print("wait the FACE model init")
                            while(True):

                                if face_modelmanage.get_init_state() == 'successed':
                                    Code.g_modelmanage_list.append(face_modelmanage)
                                    reg_re['number'] = reg_re.get('number') + 1
                                    print("FACE model init successed")
                                    break

                                elif face_modelmanage.get_init_state() == 'failed':
                                    print("FACE model init failed")
                                    break

                            break
                Resource_Info.append(reg_re)


    except:
        strlog = "init model exception! %s"%(str(traceback.format_exc()))
        OnWriteLog(strlog,level=LOG_LEVEL_ERROR)
        Resource_Info = []
        thread_pool = []
    OnWriteLog("init model end ; res = %s"%(str(Resource_Info)))
    return Resource_Info, thread_pool


def share_memery(name):

    try:
        cmd = "plasma_store -m 2000000000 -s %s"%name
        subprocess.Popen(cmd, shell=True)

    except:

        strlog = "share_memery is excption!  %s"%(str(traceback.format_exc()))
        OnWriteLog(strlog,level=LOG_LEVEL_ERROR)
        return False

    return True





def start():

    OnWriteLog("resource Resoure_Model_Work start!")
    Register_Resource_Info = []
    thread_pool = []

        # load config
    if not Code.load_config():
        OnWriteLog("load_config is error!", level=LOG_LEVEL_ERROR)
        return
    if not Code.listen_port:
        Code.listen_port = int(Random_Port())
        # -----------------------------
    if Code.ray_head_address == "":
        OnWriteLog("load config the key:ray_head_address is Null", level=LOG_LEVEL_ERROR)
        return
    # -----------------------------

    # ----------------------------
        # init plasma
    share_name = '/tmp/plasma'
    if not share_memery(share_name):
        OnWriteLog("share_memery is error !", level=LOG_LEVEL_ERROR)
        return

    # ----------------------------

    # ---------------------------
        # save the Resoure_Model_Work address
    serurl = "http://%s:%d/Resoure_Model_Work/resource/task/%s"%(Code.localIp, Code.listen_port, Code.instance_guid)
    if not set_task_communicate_address(serurl, Code.localIp, share_name):
        return

    # ----------------------------

    # ----------------------------
        # init the models
    Register_Resource_Info, thread_pool = init_model(Code.resource, Code.localIp, share_name)

    #增加优先级
    print("priority", Code.priority)
    if Code.priority == 'emergency':
        reg_re = {}
        reg_re['model_name'] = Code.MODEL_PRIORITY
        reg_re['number'] = 1
        reg_re['model_memory'] = 0
        reg_re['run_memory'] = 0
        Register_Resource_Info.append(reg_re)
    else:
        reg_re = {}
        reg_re['model_name'] = Code.MODEL_ORDINARY
        reg_re['number'] = 1
        reg_re['model_memory'] = 0
        reg_re['run_memory'] = 0
        Register_Resource_Info.append(reg_re)

   # -----------------------------
    #register the ray and resource
    if 1 == Code.rigster:
        if not regitster_ray(head_address=Code.ray_head_address, resourceinfo=Register_Resource_Info):
            OnWriteLog("register ray error", level=LOG_LEVEL_ERROR)
            return

        callbakurl = "http://%s:%d/Client/Resource_Model/%s"%(Code.localIp, Code.listen_port, Code.instance_guid)
        if not register_server(Instance_guid=Code.instance_guid, serverurl=Code.server_address,
                           callbakurl=callbakurl, ResourceInfo=Register_Resource_Info):
            return


    ## 开启zmq模式使人脸模型驻留
    from Media_Brain_Resource_Manage import Media_Brain_Resource_Zmq
    print("Media_Brain_Resource_Zmq.Resource_Rest_Zmq.......")
    ret = threading.Thread(target=Media_Brain_Resource_Zmq.Resource_Rest_Zmq)
    ret.start()


#---------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------

app = Flask(__name__)


@app.route('/')
def hello_world():

    return "Hello World!"

# ---------------------------------------  添加人脸  -----------------------------------
@app.route('/add', methods=['POST'])
def add_face():

    # json_path = '/mnt/code/face/face_tool/face_666.json'
    json_path = Code.face_path

    if not request.json or 'personInfo' not in request.json:
        return jsonify({'code':205, 'msg':'http请求参数错误'})

    add_list = request.json.get('personInfo')

    zmq_ip = Code.localIp
    zmq_port = Code.zmq_port

    try:
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.connect("tcp://%s:%s" % (zmq_ip, zmq_port))  
        print('success to connnect the server ip:%s , port:%s' % (zmq_ip, zmq_port))
    except:
        print('fail to connnect the server')
         
        return jsonify({'code':204, 'msg':'程序内部错误'})

    person_list = []

    # 统计成功失败的数量的路径
    total_pic = 0
    success_pic = 0
    fail_pic = 0

    fail_list = []

    for person in add_list:
        try:
            ID = person.get('ID')
            name = person.get('name')
            tag = person.get('tag')
            path_list = person.get('filePath')

            print('正在添加:%s...' % name)

            if not ID or not name or not path_list:
                # print('此人信息不完整')
                continue

            for path in path_list:

                total_pic += 1

                start = time.time()
                # 路径转换
                img_path = '/extstore/mah' + path
                # img_path = path

                img = cv2.imread(img_path)

                # 发送zmq对象, 进行人脸检测
                pyobj = Munch()
                pyobj.img = img
                pyobj.type = 'feature_detection'
                socket.send_pyobj(pyobj)
                zmq_result = socket.recv_pyobj().result

                # 数量为 1才入库
                if len(zmq_result.get('results')) == 1:

                    front_face = zmq_result.get('results')[0].get('front_face')

                    if front_face:
                        freatrue = zmq_result.get('results')[0].get('feature')
                        # 把信息组成一个字典
                        person_info = {}
                        person_info["ID"] = ID
                        person_info["name"] = name
                        person_info["tag"] = tag
                        person_info["path"] = path
                        person_info["freatrue"] = freatrue
                    
                        # 添加进 person_list
                        person_list.append(person_info)

                        success_pic += 1

                        end = time.time()
                        print('添加一张人脸耗时:', end - start)

                    else:
                        print('此人为侧脸, 不满足入库要求')
                        fail_pic += 1
                        fail_list.append(path)

                        

                elif len(zmq_result.get('results')) == 0:
                    fail_pic += 1
                    fail_list.append(path)
                    continue
                else:
                    fail_pic += 1
                    fail_list.append(path)
                    continue
        except:
            continue

    # 把 person_list写进人脸库
    if os.path.isfile(json_path):
        pass
    else:
        with open(json_path, 'w') as f:
            f.write("[]")

    with open(json_path, 'r', encoding='utf-8-sig') as f:
        info_list = json.load(f)
        for i in person_list:
            info_list.append(i)
    # 写数据
    with open(json_path, 'w') as f:
        json.dump(info_list, f, ensure_ascii=False)


    print('total_pic:', total_pic)
    print('success_pic', success_pic)
    print('person_list:', len(person_list))
    print('fail_pic:', fail_pic)

    print('fail_list', fail_list)

    return jsonify(
        {
            "code":200, 
            "msg":"添加人脸成功",
            "detail":{
                        "total_add_number":total_pic,
                        "success_add_number":success_pic,
                        "fail_add_number":fail_pic,
                        "fail_add_picture":fail_list
                    }       
        }
    )
            


# ---------------------------------------  删除人脸  -----------------------------------

@app.route('/delete', methods=['POST'])
def delete_face():

    json_path = Code.face_path

    if not request.args or 'ID' not in request.args:
        return jsonify({'code':205, 'msg':'http请求参数错误'})

    if os.path.isfile(json_path):
        pass
    else:
        return jsonify({"code":204, "msg":"程序内部错误"})
    
    person_id = request.args.get('ID')
 
    # 单个删除
    try:
        with open(json_path, 'r', encoding='utf-8-sig') as f:
            info_list = json.load(f)

        len_again = len(info_list)
        info_list = [i for i in info_list if i.get('ID') != person_id]
        len_after = len(info_list)
        print('删除此ID对应数据个数:', len_again - len_after)

        if len_again - len_after == 0:
            return jsonify({"code":201, "msg":"人脸库找不到此ID, 删除失败"})
        else:
            with open(json_path, 'w') as f:
                json.dump(info_list, f, ensure_ascii=False)

            return jsonify({"code":200, "msg":'删除人脸成功'})
    except:
        return jsonify({"code":201, "msg":"删除失败"})


    # 批量删除
    # # json_path = '/mnt/code/face/face_tool/face_666.json'
    # json_path = Code.face_path

    # if not request.args or 'ID' not in request.args:
    #     return jsonify({'code':205, 'msg':'http请求参数错误'})
    
    # person_list = request.json.get('ID')

    # for person_id in person_list:
    #     try:
    #         with open(json_path, 'r', encoding='utf-8-sig') as f:
    #             info_list = json.load(f)

    #         len_again = len(info_list)
    #         info_list = [i for i in info_list if i.get('ID') != person_id]
    #         len_after = len(info_list)
    #         print('删除此ID对应数据个数:', len_again - len_after)

    #         if len_again - len_after == 0:
    #             continue
    #         else:
    #             with open(json_path, 'w') as f:
    #                 json.dump(info_list, f, ensure_ascii=False)
    #     except:
    #         continue
            
    # return jsonify({"code":200, "msg":"删除人脸成功"})
    
            
# ---------------------------------------  修改人脸  -----------------------------------
@app.route('/update', methods=['POST'])
def update_face():
    '''
    修改人脸信息
    :params info: 新的人脸新的json
    return: {"code":200, "msg":"ok"}
    '''

    json_path = Code.face_path

    if not request.json or 'ID' not in request.json:
        return jsonify({'code':205, 'msg':'http请求参数错误'})


    if os.path.isfile(json_path):
        pass
    else:
        return jsonify({"code":204, "msg":"程序内部错误"})
        
    ID = request.json.get('ID')
    new_name = request.json.get('newName')
    new_tag = request.json.get('newTag')

    with open(json_path, "r", encoding='utf-8-sig') as f:
        info_list = json.load(f)
    
    picture_number = 0

    try:
        for info in info_list:
            if info.get('ID') == ID:
                if new_name:
                    info['name'] = new_name
                if new_tag:
                    info['tag'] = new_tag

                picture_number += 1
    except:
        return jsonify({"code":201, "msg":"修改失败"})

    print('此ID修改的数据量:', picture_number)
    if picture_number:
        with open(json_path, 'w') as f:
            json.dump(info_list, f, ensure_ascii=False)

        return jsonify({"code":200, "msg":"修改人脸成功"})
    else:
        return jsonify({"code":201, "msg":"没有对应ID, 修改失败"})


# ---------------------------------------  查询人脸  -----------------------------------

@app.route('/query', methods=['POST'])
def query_face():

    '''
    查询人脸信息
    return: {"code":200, "msg":"ok"}
    '''

    # json_path = '/mnt/code/face/face_tool/face_666.json'
    json_path = Code.face_path

    if not request.args or 'ID' not in request.args:
        return jsonify({'code':205, 'msg':'http请求参数错误'})
    
    ID = request.args.get('ID')

    if os.path.isfile(json_path):
        pass
    else:
        return jsonify({"code":204, "msg":"程序内部错误"})

    with open(json_path, 'r', encoding='utf-8-sig') as f:
        face_list = json.load(f)
        
        if ID != 'all':
            res = {}
            contents = {}
            for face in face_list:
                if ID == face.get('ID'):
                    print('找到查询的ID')
                    contents['ID'] = face.get('ID')
                    contents['name'] = face.get('name')
                    contents['tag'] = face.get('tag')

                    res['code'] = 200
                    res['msg'] = 'ok'
                    res['contents'] = contents

                    return jsonify(res)
            else:
                res['code'] = 201
                res['msg'] = '人脸库没有此ID,查询失败'
                res['contents'] = contents
                return jsonify(res)

        # 查询所有
        else:
            total_res = {}
            total_res['face_number'] = len(face_list)
            res_list = []

            for face in face_list:
                res = {}
                contents = {}

                contents['ID'] = face.get('ID')
                contents['name'] = face.get('name')
                contents['tag'] = face.get('tag')

                res['code'] = 200
                res['msg'] = 'ok'
                res['contents'] = contents

                res_list.append(res)

            total_res['face_list'] = res_list

            return jsonify(total_res)
            

# ---------------------------------------  人脸检测 -----------------------------------
@app.route('/recognition', methods=['POST'])
def face_recognition():

    if not request.json or 'taskGUID' not in request.json:
        return jsonify({'code':205, 'msg':'http请求参数错误'})

    task_guid = request.json.get('taskGUID')
    file_path_list = request.json.get('filePath')
    url_list = request.json.get('url')
    imgbase64 = request.json.get('imgBase64')

    if not file_path_list and not url_list and not imgbase64:
        return jsonify({'code':205, 'msg':'http请求参数错误'})

    zmq_ip = Code.localIp
    zmq_port = Code.zmq_port
    
    try:
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.connect("tcp://%s:%s" % (zmq_ip, zmq_port))  
        print('success to connnect the server ip:%s , port:%s' % (zmq_ip, zmq_port))
    except:
        print('fail to connnect the server')
        return jsonify({'code':204, 'msg':'程序内部错误'})

    
    face_list = []

    if file_path_list:
        for img_path in file_path_list:
            try:
                img = cv2.imread(img_path)
            except:
                continue
            pyobj = Munch()
            pyobj.img = img
            pyobj.type = 'face_recognition'
            socket.send_pyobj(pyobj)
            result_dict = socket.recv_pyobj().result.get('reslut')
            try:
                del result_dict['queryurl']
                del result_dict['msg']
                del result_dict['code']
            except:
                pass

            face_list.append(result_dict)

    elif url_list:
        for url in url_list:
            try:
                capture = cv2.VideoCapture(url)
                if capture.isOpened():
                    ret, img = capture.read()
            except:
                continue
            pyobj = Munch()
            pyobj.img = img
            pyobj.type = 'face_recognition'
            socket.send_pyobj(pyobj)
            result_dict = socket.recv_pyobj().result.get('reslut')
            try:
                del result_dict['queryurl']
                del result_dict['msg']
                del result_dict['code']
            except:
                pass

            face_list.append(result_dict)

    elif imgbase64:
        img_data = base64.b64decode(imgbase64)
        random_str = ''.join(random.sample('abcdefghijklmnopqrstuvwxyz0123456789',8))
        picture_dir = os.getcwd()
        if os.path.isdir(os.getcwd() + '/picture_dir'):
            pass
        else:
            os.makedirs(os.getcwd() + '/picture_dir')
            
        img_path = os.getcwd() + '/picture_dir/' + random_str + '.jpg'
        with open(img_path, "wb") as f2:
            f2.write(img_data)

        img = cv2.imread(img_path)

        pyobj = Munch()
        pyobj.img = img
        pyobj.type = 'face_recognition'
        socket.send_pyobj(pyobj)
        result_dict = socket.recv_pyobj().result.get('reslut')
        
        try:
            del result_dict['queryurl']
            del result_dict['msg']
            del result_dict['code']
        except:
            pass

        face_list.append(result_dict)
        os.remove(img_path)


    return jsonify({'taskGUID':task_guid, 'code': 200, 'result_list':face_list})

    
if __name__ == "__main__":
    start()
    time.sleep(2)
    app.run(host='0.0.0.0', port=Code.listen_port)

















