# -*- coding: utf-8 -*-

import base64
import json
import os
import random
import requests
import shutil
import sys
import time

import cv2
import numpy as np
import zmq
from flask import Flask, abort, jsonify, request
from munch import Munch

# os.system('ldconfig /usr/local/cuda-9.0/lib64')

# 添加搜索路径到sys列表以便能够导入 Media_Brain_Resource_Manage
# npos = os.getcwd().rfind("/")
# add_path = os.getcwd()[0:npos]
# sys.path.append(add_path)

# from Media_Brain_Resource_Manage.Resource_Model.FACE.face_model import FaceModel


app = Flask(__name__)







@app.route('/')
def hello_world():

    return "Hello World!"


# ---------------------------------------  添加人脸  -----------------------------------
@app.route('/add', methods=['POST'])
def add_face():

    # rest

    if not request.json or 'personInfo' not in request.json:
        # 没有指定id则返回全部
        tasks = {'message':'请求参数错误'} 
        return jsonify(tasks)

    add_list = request.json.get('personInfo')

    zmq_ip = '172.16.139.24'
    zmq_port = '10027'  
    try:
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.connect("tcp://%s:%s" % (zmq_ip, zmq_port))  
        print('success to connnect the server ip:%s , port:%s' % (zmq_ip, zmq_port))
    except:
        print('fail to connnect the server')
        tasks = {'message':'连接zmq失败'} 
        return jsonify(tasks)

    for person in add_list:
        try:
            ID = person.get('ID')
            name = person.get('name')
            group = person.get('group')
            note = person.get('note')

            # 拼接要创建的group目录
            group =  group[0:-1] if group.endswith('/') else group
            new_path = os.getcwd() + '/人脸库' + group + '/'  + name      # 可以根据目录自动拼接
            # 检测是否存在
            if os.path.isdir(new_path):
                print('人脸group路径存在, 不需要创建')
            else:
                os.makedirs(new_path)
                print('人脸group路径不存在, 创建新的人脸group成功')

            # 同级目录下放json的路径
            json_path = new_path + '/' + name  + '.json'


            # 生成随机图片名

            # random_str = ''.join(random.sample('abcdefghijklmnopqrstuvwxyz0123456789',8))
            # img_path = new_path + '/' + name + '_' + random_str + '.jpg'

            if person.get('filePath'):
                filePath_list = person.get('filePath')
                for per in filePath_list:
                    start = time.time()

                    random_str = ''.join(random.sample('abcdefghijklmnopqrstuvwxyz0123456789',8))
                    img_path = new_path + '/' + name + '_' + random_str + '.jpg'

                    img = cv2.imread(per)
                    cv2.imwrite(img_path, img)

                    print('写入图片成功')
                    print('路径配置完成, 准备检测人脸')
                    
                    # 读出新路径的图, 去检测
                    img = cv2.imread(img_path)

                    # 发送zmq对象, 进行人脸检测
                    pyobj = Munch()
                    pyobj.img = img
                    pyobj.type = 'feature_detection'
                    socket.send_pyobj(pyobj)
                    zmq_result = socket.recv_pyobj().result
                    if len(zmq_result.get('results')) == 1:
                        freatrue = zmq_result.get('results')[0].get('feature')
                        bbox = zmq_result.get('results')[0].get('bbox')
                        print('len(freatrue):', len(freatrue))

                        # 把信息组成一个字典
                        sou_info = {}
                        if os.path.isfile(img_path):
                            sou_info["ID"] = ID
                            sou_info["name"] = name
                            sou_info["group"] = group
                            sou_info["note"] = note
                            print('sou_info', sou_info)
                            data = []
                            single_data = {"path":img_path, "feature":freatrue}
                            data.append(single_data)
                            sou_info["data"] = data
                        else:
                            return jsonify({"code":201, "msg":"添加人脸失败"})
                                
                        # 判断json_path是否存在, 没有则新建, 有则把新的feature添加到data字段里面
                        if os.path.isfile(json_path):
                            try:
                                with open(json_path, "r", encoding='utf-8-sig') as f:
                                    info_list = json.load(f)
                                    data_list = info_list[0].get('data')
                                    print('当前人脸(feature)数量:', len(data_list))
                                    data_list.append(single_data)

                                with open(json_path, "w") as f:
                                    json.dump(info_list, f, ensure_ascii=False)

                                # 检测是否成功
                                with open(json_path, "r", encoding='utf-8-sig') as f:
                                    info_list = json.load(f)
                                    data_list = info_list[0].get('data')
                                    print('添加后人脸(feature)数量:', len(data_list))

                                # return 1    

                            except:
                                return jsonify({"code":201, "msg":"添加人脸失败"})

                        # 新建一个人物对应的json, 添加该人脸第一次信息
                        else:
                            print('正在新建该人脸json')
                            try:
                                with open(json_path, "w") as f:
                                    f.write("[]")
                                with open(json_path, "r", encoding='utf-8-sig') as f:
                                    info_list = json.load(f)
                                    info_list.append(sou_info)
                                with open(json_path, "w") as f:
                                    json.dump(info_list, f, ensure_ascii=False)

                                # return 1    
                            except:
                                return jsonify({"code":201, "msg":"添加人脸失败"})


                        end = time.time()
                        print('添加一张人脸耗时:', end - start)


                    elif len(zmq_result.get('results')) == 0:
                        continue
                        # return jsonify({'message':'未检测到人脸, 添加人脸失败'})
                    else:
                        continue
                        # return jsonify({'message':'图片人脸数量大于一个, 添加人脸失败'})



            elif person.get('url'):
                url_list = person.get('url')
                for per in url_list:
                    start = time.time()

                    random_str = ''.join(random.sample('abcdefghijklmnopqrstuvwxyz0123456789',8))
                    img_path = new_path + '/' + name + '_' + random_str + '.jpg'

                    capture = cv2.VideoCapture(per)
                    if capture.isOpened():
                        ret, img = capture.read() 
                        cv2.imwrite(img_path, img)
                        print('url写入图片成功')
                    else:
                        print('url读取失败')

                    print('路径配置完成, 准备检测人脸')

                    # 读出新路径的图, 去检测
                    img = cv2.imread(img_path)

                    # 发送zmq对象, 进行人脸检测
                    pyobj = Munch()
                    pyobj.img = img
                    pyobj.type = 'feature_detection'
                    socket.send_pyobj(pyobj)
                    zmq_result = socket.recv_pyobj().result
                    if len(zmq_result.get('results')) == 1:
                        freatrue = zmq_result.get('results')[0].get('feature')
                        bbox = zmq_result.get('results')[0].get('bbox')
                        print('len(freatrue):', len(freatrue))

                        # 把信息组成一个字典
                        sou_info = {}
                        if os.path.isfile(img_path):
                            sou_info["ID"] = ID
                            sou_info["name"] = name
                            sou_info["group"] = group
                            sou_info["note"] = note
                            print('sou_info', sou_info)
                            data = []
                            single_data = {"path":img_path, "feature":freatrue}
                            data.append(single_data)
                            sou_info["data"] = data
                        else:
                            return jsonify({"code":201, "msg":"添加人脸失败"})
                                
                        # 判断json_path是否存在, 没有则新建, 有则把新的feature添加到data字段里面
                        if os.path.isfile(json_path):
                            try:
                                with open(json_path, "r", encoding='utf-8-sig') as f:
                                    info_list = json.load(f)
                                    data_list = info_list[0].get('data')
                                    print('当前人脸(feature)数量:', len(data_list))
                                    data_list.append(single_data)

                                with open(json_path, "w") as f:
                                    json.dump(info_list, f, ensure_ascii=False)

                                # 检测是否成功
                                with open(json_path, "r", encoding='utf-8-sig') as f:
                                    info_list = json.load(f)
                                    data_list = info_list[0].get('data')
                                    print('添加后人脸(feature)数量:', len(data_list))

                                # return 1    

                            except:
                                return jsonify({"code":201, "msg":"添加人脸失败"})

                        # 新建一个人物对应的json, 添加该人脸第一次信息
                        else:
                            print('正在新建该人脸json')
                            try:
                                with open(json_path, "w") as f:
                                    f.write("[]")
                                with open(json_path, "r", encoding='utf-8-sig') as f:
                                    info_list = json.load(f)
                                    info_list.append(sou_info)
                                with open(json_path, "w") as f:
                                    json.dump(info_list, f, ensure_ascii=False)

                                # return 1    
                            except:
                                return jsonify({"code":201, "msg":"添加人脸失败"})


                        end = time.time()
                        print('添加一张人脸耗时:', end - start)


                    elif len(zmq_result.get('results')) == 0:
                        continue
                        # return jsonify({'message':'未检测到人脸, 添加人脸失败'})
                    else:
                        continue
                        # return jsonify({'message':'图片人脸数量大于一个, 添加人脸失败'})



            

            elif person.get('Base64'):
                bs64_list = person.get("Base64")
                for per in bs64_list:
                    start = time.time()
                    img_data = base64.b64decode(per)
                    random_str = ''.join(random.sample('abcdefghijklmnopqrstuvwxyz0123456789',8))
                    img_path = new_path + '/' + name + '_' + random_str + '.jpg'
          
                    with open(img_path, "wb") as f2:
                        f2.write(img_data)
                    print('base64写入图片成功')
                    print('路径配置完成, 准备检测人脸')
            
                    # 读出新路径的图, 去检测
                    img = cv2.imread(img_path)

                    # 发送zmq对象, 进行人脸检测
                    pyobj = Munch()
                    pyobj.img = img
                    pyobj.type = 'feature_detection'
                    socket.send_pyobj(pyobj)
                    zmq_result = socket.recv_pyobj().result

                    if len(zmq_result.get('results')) == 1:
                        freatrue = zmq_result.get('results')[0].get('feature')
                        bbox = zmq_result.get('results')[0].get('bbox')
                        print('len(freatrue):', len(freatrue))

                        # 把信息组成一个字典
                        sou_info = {}
                        if os.path.isfile(img_path):
                            sou_info["ID"] = ID
                            sou_info["name"] = name
                            sou_info["group"] = group
                            sou_info["note"] = note
                            print('sou_info', sou_info)
                            data = []
                            single_data = {"path":img_path, "feature":freatrue}
                            data.append(single_data)
                            sou_info["data"] = data
                        else:
                            return jsonify({"code":201, "msg":"添加人脸失败"})
                                
                        # 判断json_path是否存在, 没有则新建, 有则把新的feature添加到data字段里面
                        if os.path.isfile(json_path):
                            try:
                                with open(json_path, "r", encoding='utf-8-sig') as f:
                                    info_list = json.load(f)
                                    data_list = info_list[0].get('data')
                                    print('当前人脸(feature)数量:', len(data_list))
                                    data_list.append(single_data)

                                with open(json_path, "w") as f:
                                    json.dump(info_list, f, ensure_ascii=False)

                                # 检测是否成功
                                with open(json_path, "r", encoding='utf-8-sig') as f:
                                    info_list = json.load(f)
                                    data_list = info_list[0].get('data')
                                    print('添加后人脸(feature)数量:', len(data_list))

                                # return 1    

                            except:
                                return jsonify({"code":201, "msg":"添加人脸失败"})

                        # 新建一个人物对应的json, 添加该人脸第一次信息
                        else:
                            print('正在新建该人脸json')
                            try:
                                with open(json_path, "w") as f:
                                    f.write("[]")
                                with open(json_path, "r", encoding='utf-8-sig') as f:
                                    info_list = json.load(f)
                                    info_list.append(sou_info)
                                with open(json_path, "w") as f:
                                    json.dump(info_list, f, ensure_ascii=False)

                                # return 1    
                            except:
                                return jsonify({"code":201, "msg":"添加人脸失败"})


                        end = time.time()
                        print('添加一张人脸耗时:', end - start)


                    elif len(zmq_result.get('results')) == 0:
                        continue
                        # return jsonify({'message':'未检测到人脸, 添加人脸失败'})
                    else:
                        continue
                        # return jsonify({'message':'图片人脸数量大于一个, 添加人脸失败'})



        except:
            print('图片参数有误')
            continue


    

    # 全部成功则更新json库
    create_face_suoyin()

    return jsonify({"code":200, "msg":"添加人脸成功"})
            


# ---------------------------------------  删除人脸  -----------------------------------

@app.route('/delete', methods=['POST'])
def delete_face():

    if not request.args or 'ID' not in request.args:
        # 没有指定id则返回全部
        tasks = {'message':'请求参数错误'}
        return jsonify(tasks)
    
    person_id = request.args.get('ID')

    # 遍历所有的json文件名,放进一个列表 
    json_list = []
    for dirpath, dirnames, filenames in os.walk(os.getcwd()+'/人脸库'):
            for filename in filenames:
                if '.json' in filename:
                    abs_filename = os.path.join(dirpath,filename)
                    json_list.append(abs_filename)

    print(json_list)

    # 单个删除
    
    for path in json_list:
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                info_list = json.load(f)
                if person_id == info_list[0].get('ID'):
                    print('找到对应ID, 准备从人脸库删除对应人物')
                    dir_name = os.path.dirname(path)
                    if dir_name:
                        shutil.rmtree(dir_name)
                        print('-' * 100)
                        print('删除%s成功' % dir_name)
                        print('-' * 100)

                        create_face_suoyin()
                        return jsonify({"code":200, "msg":"删除人脸成功, ID:%s" % person_id})
                        # break
        except:
            print('open %s error' % path)
            return jsonify({"code":201, "msg":"删除失败"})
    else:
        return jsonify({"code":201, "msg":"人脸库找不到此ID, 无法删除"})





    # 批量删除
    # if not request.json or 'ID' not in request.json:
    #     # 没有指定id则返回全部
    #     tasks = {'message':'请求参数错误'}
    #     return jsonify(tasks)
    
    # person_list = request.json.get('ID')

    # # 遍历所有的json文件名,放进一个列表 
    # json_list = []
    # for dirpath, dirnames, filenames in os.walk(os.getcwd()+'/人脸库'):
    #         for filename in filenames:
    #             if '.json' in filename:
    #                 abs_filename = os.path.join(dirpath,filename)
    #                 json_list.append(abs_filename)

    # print(json_list)


    # empty_list = []

    # for person_id in person_list:

    #     for path in json_list:
    #         try:
    #             with open(path, 'r', encoding='utf-8-sig') as f:
    #                 info_list = json.load(f)
    #                 if person_id == info_list[0].get('ID'):
    #                     print('找到对应ID, 准备从人脸库删除对应人物')
    #                     dir_name = os.path.dirname(path)
    #                     if dir_name:
    #                         shutil.rmtree(dir_name)
    #                         print('删除%s成功' % dir_name)
    #                         json_list.remove(path)
    #                         break

    #         except:
    #             print('open %s error' % path)
    #     else:
    #         empty_list.append(person_id)

    # if empty_list:
    #     msg = '人脸库里找不到的ID:%s' % str(empty_list)
    #     return jsonify({"code":201, "msg":msg})
    # else:
    #     return jsonify({"code":200, "msg":"ok"})
        

            

                
        
# ---------------------------------------  修改人脸  -----------------------------------
@app.route('/update', methods=['POST'])
def update_face():
    '''
    修改人脸信息
    :params info: 新的人脸新的json
    return: {"code":200, "msg":"ok"}
    '''

    if not request.json or 'ID' not in request.json:
        # abort(400)
        return jsonify({"code":202, "msg":"参数错误"})
        

    ID = request.json.get('ID')
    new_group = request.json.get('newGroup')
    new_name = request.json.get('newName')
    new_note = request.json.get('newNote')

    # 遍历json列表
    json_list = []
    for dirpath, dirnames, filenames in os.walk(os.getcwd()+'/人脸库'):
            for filename in filenames:
                if '.json' in filename:
                    abs_filename = os.path.join(dirpath,filename)
                    json_list.append(abs_filename)

    print()
    print('json_list:')
    print(json_list)
    print()

    for path in json_list:
        name_flag = 0
        # try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            info_list = json.load(f)

        if ID == info_list[0].get('ID'):
            print('--------------------找到对应ID, 准备从人脸库修改人物信息------------------')

            # 先修改 json

            if new_note:
                info_list[0]['note'] = new_note        
                print('成功修改json的note')

            if new_name:
                old_name = info_list[0].get('name')
                info_list[0]['name'] = new_name    
                # info_list[0]['data'][0]['path'] = new_name            
                print('成功修改json的name')

                if new_group:
                    new_path = os.getcwd()+'/人脸库' + new_group + '/' + new_name
                    for i in info_list[0].get('data'):
                        new_pa = new_path + '/' + i.get('path').split('/')[-1]
                        # print(new_pa)
                        new_pa = new_pa.replace(old_name+'_', new_name+'_')
                        # print(new_pa)
                        i['path'] = new_pa
                        
                    print('成功修改json里面的path')

                else:
                    for i in info_list[0].get('data'):
                        old_path = i.get('path')
                        new_path = old_path.replace(old_name, new_name)
                        i['path'] = new_path
                        
                print('成功修改json里面的path')



                    

            if new_group:
                old_group = info_list[0].get('group')
                info_list[0]['group'] = new_group
                if not new_name:
                    for i in info_list[0].get('data'):
                        old_path = i.get('path')
                        new_path = old_path.replace(old_group, new_group)
                        i['path'] = new_path
                    

                print('成功修改json的group')
                

            
                

            print('正准备打开文件写入新的json')
            with open(path, 'w') as g:
                json.dump(info_list, g, ensure_ascii=False)
                print('重新生成json文件')
            print('写入成功')

            # 修改人名的话要修改三部分
            if new_name:            
                ## ---------------------------  修改图片名字 -----------------------------
                person_dir = os.path.dirname(path)
                file_list = os.listdir(person_dir)
                pic_list = [x for x in file_list if '.json' not in x]       # 得到图片名的列表
                for pic in pic_list:
                    old_p = person_dir + '/' + pic 
                    new_p = person_dir + '/' + new_name + '_' + old_p.split('/')[-1].split('_')[-1] 
                    if os.path.exists(old_p):
                        os.rename(old_p, new_p)
                        print('成功修改图片名')

                ## ---------------------------  修改json名字 -----------------------------
                print('开始修改json的名字')
                old_j =  path
                new_j =  os.path.dirname(path) + '/' + new_name + '.json'
                if os.path.exists(old_j):
                    os.rename(old_j, new_j)
                    print('修改json名字成功')

                

                ## ---------------------------  修改文件夹人名 -----------------------------
                old_dir = os.path.dirname(path)
                new_dir = os.path.dirname(old_dir) + '/' + new_name
                if os.path.exists(old_dir):
                    shutil.move(old_dir, new_dir)
                    name_flag = 1
                    print('修改人名文件夹成功')



            # 移动文件夹
            if new_group:  
                old_name = info_list[0].get('name')
                old_g = new_dir if name_flag else os.path.dirname(path)
                if new_name:
                    new_g = os.getcwd()+'/人脸库' + new_group + '/' + new_name
                else:
                    new_g = os.getcwd()+'/人脸库' + new_group + '/' + old_name
                if os.path.exists(old_g):
                    shutil.move(old_g, new_g)
                    print('移动文件夹成功')

            
            print('--------------------  修改信息成功 ------------------')
            create_face_suoyin()
            return jsonify({"code":200, "msg":"ok"})

        # except:
        #     print('open %s error' % path)

    
    return jsonify({"code":201, "msg":"没有对应ID, 更新失败"})




# ---------------------------------------  查询人脸  -----------------------------------

@app.route('/query', methods=['POST'])
def query_face():

    '''
    查询人脸信息
    return: {"code":200, "msg":"ok"}
    '''
    if not request.args or 'ID' not in request.args:
        # 没有指定id则返回全部
        tasks = {'message':'请求参数错误'}
        return jsonify(tasks)
    
    id = request.args.get('ID')

    face_path =  os.getcwd() + '/最终人脸json/face.json'

    if os.path.isfile(face_path):
        pass
    else:
        return jsonify({"code":202, "message":"人脸库不存在"})

    with open(face_path, 'r', encoding='utf-8-sig') as f:
        face_list = json.load(f)
        
        if id != '0':
            res = {}
            contents = {}
            for face in face_list:
                if id == face.get('ID'):
                    print('找到查询的ID')
                    contents['ID'] = face.get('ID')
                    contents['name'] = face.get('name')
                    contents['group'] = face.get('group')
                    contents['note'] = face.get('note')

                    res['code'] = 200
                    res['message'] = 'ok'
                    res['contents'] = contents

                    return jsonify(res)

            else:
                res['code'] = 201
                res['message'] = '人脸库没有此ID'
                res['contents'] = contents
                return jsonify(res)
        else:
            total_res = {}
            total_res['face_number'] = len(face_list)
            res_list = []

            for face in face_list:
                res = {}
                contents = {}

                contents['ID'] = face.get('ID')
                contents['name'] = face.get('name')
                contents['group'] = face.get('group')
                contents['note'] = face.get('note')

                res['code'] = 200
                res['message'] = 'ok'
                res['contents'] = contents

                res_list.append(res)

            total_res['face_list'] = res_list

            return jsonify(total_res)
            


# ---------------------------------------  合并所有人脸信息 -----------------------------------

def create_face_suoyin():
    # 遍历json列表
    json_list = []
    for dirpath, dirnames, filenames in os.walk(os.getcwd()+'/人脸库'):
        for filename in filenames:
            if '.json' in filename:
                abs_filename = os.path.join(dirpath,filename)
                json_list.append(abs_filename)

    print()
    print('json_list:')
    print('人脸json数量:', len(json_list))
    for i in json_list:
        print(i)
    print()

    face_dir = os.getcwd()+'/最终人脸json/'
    if os.path.isdir(face_dir):
        pass
    else:
        os.makedirs(face_dir)

    face_path = face_dir + 'face.json'

    with open(face_path, "w") as f:
        f.write("[]")
    with open(face_path, "r", encoding='utf-8-sig') as f:
        total_list = json.load(f)


    for js in json_list:
        person = {}

        try:

            with open(js, "r", encoding='utf-8-sig') as f:
                info_list = json.load(f)

                person['ID'] = info_list[0].get('ID')
                person['name'] = info_list[0].get('name')
                person['group'] = info_list[0].get('group')
                person['note'] = info_list[0].get('note')

                data_list = info_list[0].get('data')
                if data_list:
                    for data in data_list:
                        person['path'] = data.get('path')
                        person['freatrue'] = data.get('feature')

                        total_list.append(person)

        except:
            print('open %s is error' % js)
            continue  

    with open(face_path, "w") as f:
        json.dump(total_list, f, ensure_ascii=False)
        print('最终json写入成功')

    return 1    



# ---------------------------------------  人脸检测 -----------------------------------
@app.route('/recognition', methods=['POST'])
def face_recognition():

    if not request.json or 'taskGUID' not in request.json:
        # 没有指定id则返回全部
        tasks = {'message':'请求参数错误'} 
        return jsonify(tasks)

    task_guid = request.json.get('taskGUID')
    file_path_list = request.json.get('filePath')
    url_list = request.json.get('url')
    imgbase64 = request.json.get('imgBase64')

    if not file_path_list and not url_list and not imgbase64:
        tasks = {'message':'请求参数错误'} 
        return jsonify(tasks)


    zmq_ip = '172.16.139.24'
    zmq_port = '10027'  
    try:
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.connect("tcp://%s:%s" % (zmq_ip, zmq_port))  
        print('success to connnect the server ip:%s , port:%s' % (zmq_ip, zmq_port))
    except:
        print('fail to connnect the server')
        tasks = {'message':'连接zmq失败'} 
        return jsonify(tasks)

    
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
        if os.path.isdir(os.getcwd() + '/picture'):
            pass
        else:
            os.makedirs(os.getcwd() + '/picture')
            
        img_path = os.getcwd() + '/picture/' + random_str + '.jpg'
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

    app.run(host='0.0.0.0', port=5566)
   


