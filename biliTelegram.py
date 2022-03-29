import requests
import json
from typing import Tuple, List
import sys
import os
import traceback
import nonebot
from nonebot.log import logger
from nonebot.adapters.onebot.v11 import MessageSegment


__PLUGIN_NAME = "B站整合~影视/番剧"
biliTeleInfoUrl = 'https://api.bilibili.com/pgc/web/season/section?season_id={}'
getSeasonIDAPI = 'https://api.bilibili.com/pgc/view/web/season?ep_id={}'
getEpisodesAPI = 'https://api.bilibili.com/pgc/web/season/section?season_id={}'
telegramDir = './src/plugins/nonebot_plugin_bilibilibot/file/telegram/'

header = {
    'User-Agent':'Mozilla/5.0 (Windows NT 6.1; rv2.0.1) Gecko/20100101 Firefox/4.0.1'
}

FollowTelegramFile = '/root/project/NoneBot/TDK_Bot/src/file/FollowedTelegram.json'

def GetTelegramInfo(seasonID: str, index: int) -> Tuple[bool, int, str, str, str]:
    """
    @description  :
    获取影视区作品的更新情况
    ---------
    @param  :
    seasonID: 影视区作品的id
    index: 文件记录中的最新一集
    -------
    @Returns  :
    返回一个元组
    (是否更新, 最新集数, 最新集标题, 最新集链接, 封面链接)
    -------
    """
    
    response = requests.get(url=getEpisodesAPI.format(seasonID), headers=header)
    assert response.status_code == 200, '查询影视{}信息连接错误，status_code = {}'.format(response.status_code)

    response = json.loads(response.text)

    if response['code'] == 0:
        episodes = response['result']['main_section']['episodes']
        if len(episodes) > index:
            # 影视有更新
            latestEpisode = episodes[-1]
            coverURL = latestEpisode['cover']
            title = latestEpisode['long_title']
            playURL = latestEpisode['share_url']
            return (True, len(episodes), title, playURL, coverURL)
        else:
            return (False, 0, '', '', '')
    else:
        logger.debug(f"[{__PLUGIN_NAME}]查询的影视片不存在")
        return (False, 0, '', '', '')

def GetSeasonIDByEpid(epID: str) -> Tuple[bool, str, str, int]:
    """
    @description  :
    根据单集的epid，获取整季的seasonID以及名字
    ---------
    @param  :
    epid: 单集的epid
    -------
    @Returns  :
    返回一个元组
    [isSuccess, seasonID, seasonTitle, latestIndex]
    
    -------
    """
    res = requests.get(url=getSeasonIDAPI.format(epID), headers=header)
    assert res.status_code == 200, f'获取seasonID时发生连接错误，status_code = {res.status_code}'

    res = json.loads(res.text)
    if res['code'] == 0:
        seasonID = str(res['result']['season_id'])
        seasonTitle = res['result']['season_title']
        latestIndex = len(res['result']['episodes'])

        return (True, seasonID, seasonTitle, latestIndex)
    else:
        logger.debug(f'{__PLUGIN_NAME}获取seasonID失效，请检查epid')
        return (False, '', '', 0)

    
async def CheckTeleUpdate():
    """
    @description  :
    检查文件中的每一个影视节目是否更新，如果更新则向用户发送通知，并且更新文件
    ---------
    @param  :
    无
    -------
    @Returns  :
    无
    -------
    """
    telegramFiles = os.listdir(telegramDir)
    for filename in telegramFiles:
        with open(telegramDir + '/' + filename, 'r+') as f:
            info = json.load(f)
            # [telegramName, latestIndex, [followers]]
            schedBot = nonebot.get_bot()
            shouldUpdated = False
            epID = filename.split('.')[0]
            
            try:
                res = GetTelegramInfo(epID, info[1])
                if res[0]:
                    logger.debug(f'{__PLUGIN_NAME}检测到影视剧{info[0]}更新')
                    
                    shouldUpdated = True
                    info[1] = res[1]
                    textMsg = "【B站动态】\n《{}》已更新第{}集\n标题: {}\n链接: {}\n".format(
                        info[0], res[1], res[2], res[3]
                    )
                    coverMsg = MessageSegment.image(res[4])
                    logger.debug(f'{__PLUGIN_NAME}向关注用户发送更新通知')
                    
                    for follower in info[2]:
                        await schedBot.send_msg(message=textMsg + coverMsg, user_id=follower)
                    logger.info(f"[{__PLUGIN_NAME}]通知用户节目《{info[0]}》已更新第{res[1]}集")
            except Exception as e:
                ex_type, ex_val, _ = sys.exc_info()
                exceptionMsg = '【错误报告】\n检测节目《{}》时发生错误\n错误类型: {}\n错误值: {}\n'.format(info[0], ex_type, ex_val)
                logger.error(f"{__PLUGIN_NAME}\n" + exceptionMsg + traceback.format_exc())
            else:
                if shouldUpdated:
                    f.seek(0)
                    f.truncate()
                    json.dump(info, f)
                    logger.info(f"[{__PLUGIN_NAME}]文件FollowTelegramFile已更新！")

async def FollowModifyTelegramFile(epID: str, userID: str) -> Tuple[bool, str]:
    """
    @description  :
    根据用户关注节目，修改节目的文件
    ---------
    @param  :
    epID: 节目的ID
    userID: 用户的qq号
    -------
    @Returns  :
    返回一个元组
    [isSuccess, telegramName | '']
    -------
    """ 

    if not epID.isdigit():
        logger.debug(f'{__PLUGIN_NAME}存在错误参数{epID}')
        return (False, epID + "(错误参数)")
    try:
        res = GetSeasonIDByEpid(epID)
    except Exception:
        ex_type, ex_val, _ = sys.exc_info()
        exceptionMsg = '【错误报告】\n根据epID:{}获取seasonID时发生错误\n错误类型: {}\n错误值: {}\n'.format(epID, ex_type, ex_val)
        logger.error(f"{__PLUGIN_NAME}\n" + exceptionMsg + traceback.format_exc())
        return (False, epID + "(网络错误)")
    else:
        if res[0]:
            telegramFile = f"./src/plugins/nonebot_plugin_bilibilibot/file/telegram/{res[1]}.json"
            if os.path.exists(telegramFile):
                logger.debug(f'{__PLUGIN_NAME}节目{res[2]}文件已经存在')
                with open(telegramFile) as f:
                    telegramInfo: List = json.load(f)
                    # telegramInfo = [telegramTitle, latestIndex, [followers]]
                    logger.debug(f'{__PLUGIN_NAME}正在读取节目文件{telegramFile}')

                    if userID not in telegramInfo[2]:
                        telegramInfo[2].append(userID)
                        logger.debug(f'{__PLUGIN_NAME}用户{userID}关注节目{res[2]}成功')
                        f.seek(0)
                        f.truncate()
                        json.dump(telegramFile, f)
                        return (True, res[2] + f"(seasonID: {res[1]})")
                    else:
                        logger.debug(f'{__PLUGIN_NAME}用户{userID}已关注节目{res[2]}')
                        return (False, res[2] + "(已关注)")
            else:
                logger.debug(f'{__PLUGIN_NAME}节目{res[2]}文件不存在')
                telegramInfo = [res[2], res[3], [userID]]
                with open(telegramFile, "w+") as f:
                    json.dump(telegramInfo, f, ensure_ascii=False)
                logger.debug(f'{__PLUGIN_NAME}已创建节目{res[2]}文件')
                logger.debug(f'{__PLUGIN_NAME}用户{userID}关注主播{res[2]}成功')
                return (True, res[2] + f"(seasonID: {res[1]})")       
        else:
            logger.debug(f'{__PLUGIN_NAME}')
            return (False, epID + "(错误的epID)")
        

async def UnfollowModifyTelegramFile(seasonID: str, userID: str) -> Tuple[bool, str]:
    """
    @description  :
    根据用户取关节目，修改节目文件
    ---------
    @param  :
    seasonID: 节目的ID  
    userID: 用户的qq号
    -------
    @Returns  :
    返回一个元组
    [isSuccess, seasonTitle | seasonID(reason)]
    -------
    """
    if not seasonID.isdigit():
        return (False, seasonID + "(错误参数)")
    
    telegramFile = f"./src/plugins/nonebot_plugin_bilibilibot/file/telegram/{seasonID}.json"
    if os.path.exists(telegramFile):
        with open(telegramFile, "r+") as f:
            telegramInfo: List = json.load(f)
            # telegramInfo = [telegramTitle, latestIndex, [followers]]
            logger.debug(f'{__PLUGIN_NAME}正在读取节目{telegramInfo[0]}文件')
            if userID not in telegramInfo[2]:
                logger.debug(f'{__PLUGIN_NAME}用户{userID}未关注节目{telegramInfo[0]}')
                return (False, seasonID + "未关注")
            else:
                telegramInfo[2].remove(userID)
                if telegramInfo[2]:
                    f.seek(0)
                    f.truncate()
                    json.dump(telegramInfo, f)
                else:
                    logger.debug(f'{__PLUGIN_NAME}节目{telegramInfo[0]}已经无人关注，将文件删除')
                    os.remove(telegramFile)

                logger.debug(f'{__PLUGIN_NAME}用户{userID}取关节目{telegramInfo[0]}成功')
                return (True, telegramInfo[0] + f"(seasonID: {seasonID})")
    else:
        logger.debug(f'{__PLUGIN_NAME}用户{userID}未关注节目{seasonID}')
        return (False, seasonID + "(未关注)")
        
                
                    
                

            
            

        
    
            
