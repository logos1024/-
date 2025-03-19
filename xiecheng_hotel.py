from DrissionPage import ChromiumPage
import csv
import time
import json

class HotelScraper:
    def __init__(self):
        self.csv_file = open('nj_hotel_data.csv', mode='w', encoding='utf-8', newline='')
        self.writer = csv.DictWriter(self.csv_file, fieldnames=[
            '酒店', '星级', '位置', '区域', '经度', '纬度', '评分'
        ])
        #填入所需采集的元素
        self.writer.writeheader()

        self.dp = ChromiumPage()
        self.dp.listen.start('soa2/31454/json')  # 启动数据包监听
        self.page = 1
        self.max_retries = 5
        self._setup_browser()
        self.empty_counter = 0  # 新增空数据计数器

    def _setup_browser(self):
        self.dp.get(
            'https://hotels.ctrip.com/hotels/list?countryId=1&city=12&&highPrice=-1&barCurr=CNY&hotPoi=&sort=1&location=1046')
        #网址，按需调整

    def _is_valid_hotel(self, hotel_data):
        """增强数据验证逻辑"""
        required_fields = [
            ('hotelInfo', 'nameInfo', 'name'),
            ('hotelInfo', 'positionInfo', 'address'),
            ('hotelInfo', 'positionInfo', 'mapCoordinate')
        ]

        # 检查必要字段
        for *path, key in required_fields:
            data = hotel_data
            for p in path:
                data = data.get(p, {})
            if not data.get(key):
                return False

        # 过滤推荐酒店
        try:
            exposure = json.loads(hotel_data.get('data-exposure', '{}'))
            if 'recomhotellist' in exposure.get('ubtKey', ''):
                print("发现推荐酒店，已过滤")
                return False
        except:
            pass

        return True

    def _scroll_load(self):
        """滚动加载模式"""
        print("使用滚动加载方式...")
        self.dp.scroll.to_bottom()
        time.sleep(3)
        self.dp.scroll.up(200)
        time.sleep(1)
        return self._load_data('scroll')

    def _extract_hotel_data(self, json_data):
        """增强数据提取逻辑"""
        # 检查页面干扰元素但不终止
        if self.dp.ele('css:p.nothing', timeout=0.5) or self.dp.ele('css:.compensate-title', timeout=0.5):
            print("检测到干扰元素，继续尝试获取有效数据...")

        hotel_list = json_data.get('data', {}).get('hotelList', [])
        valid_count = 0

        for hotel in hotel_list:
            try:
                if not self._is_valid_hotel(hotel):
                    continue

                info = hotel.get('hotelInfo', {})
                position = info.get('positionInfo', {})
                comment = info.get('commentInfo', {})

                dit = {
                    '酒店': info.get('nameInfo', {}).get('name', 'N/A'),
                    '星级': info.get('hotelStar', {}).get('star', 'N/A'),
                    '位置': position.get('address', 'N/A'),
                    '区域': position.get('zoneNames', ['N/A'])[0],
                    '经度': position.get('mapCoordinate', [{}])[0].get('longitude', 'N/A'),
                    '纬度': position.get('mapCoordinate', [{}])[0].get('latitude', 'N/A'),
                    '评分': comment.get('commentScore', 'N/A')
                }
                self.writer.writerow(dit)
                valid_count += 1
                print(dit)
            except Exception as e:
                print(f"数据提取异常: {e}")

        # 更新空数据计数器
        if valid_count == 0:
            self.empty_counter += 1
        else:
            self.empty_counter = 0

        return valid_count > 0

    def _load_data(self, mode):
        """增强数据加载方法"""
        for retry in range(self.max_retries):
            print(f"数据加载尝试 {retry + 1}/{self.max_retries}")
            resp = self.dp.listen.wait(timeout=30)

            if not resp:
                print("未收到数据响应")
                continue

            # 确保响应体有效
            if not hasattr(resp, 'response') or not isinstance(resp.response.body, dict):
                print("响应数据格式异常")
                continue

            # 正确获取并命名数据
            json_data = resp.response.body  # 先赋值再使用

            # 检查必要字段
            if not json_data.get('data'):
                print("响应数据缺少data字段")
                continue

            # 提取有效数据
            return self._extract_hotel_data(json_data)

        print("达到最大重试次数")
        return False

    def _button_load(self):
        """增强按钮加载逻辑"""
        print("尝试按钮加载方式...")
        try:
            # 智能等待按钮出现
            btn = None
            start_time = time.time()
            while time.time() - start_time < 8:  # 延长等待时间至30秒
                self.dp.scroll.to_bottom()
                time.sleep(2)
                btn = self.dp.ele('css:.btn-box span', timeout=3)
                if btn and btn.text in ['搜索更多酒店', '更多推荐酒店']:
                    break
                print("按钮未找到，滚动页面重试...")
                self.dp.scroll.up(500)
                time.sleep(2)

            if not btn or btn.text not in ['搜索更多酒店', '更多推荐酒店']:
                print("未找到有效按钮")
                return False

            # 执行点击
            btn.click(by_js=True)
            print("已点击翻页按钮，等待数据加载...")

            # 动态等待加载完成
            start_time = time.time()
            while time.time() - start_time < 60:  # 延长至60秒
                if self.dp.ele('css:.loading', timeout=1):
                    print("检测到加载状态，等待...")
                    time.sleep(5)
                else:
                    # 检查是否有新数据
                    if self.dp.ele('css:.list-item-target', timeout=2):
                        print(f"第{self.page}页数据预载")
                        break
                    print("无新数据加载，继续等待...")
                    time.sleep(3)

            # 滚动定位优化
            self.dp.scroll.to_bottom()
            time.sleep(1)
            self.dp.scroll.up(400)
            time.sleep(1)

            return self._load_data('button')

        except Exception as e:  # 新增异常捕获
            print(f"按钮操作失败: {str(e)}")
            return False

    def _check_final_page(self):
        """最终页判断逻辑优化"""
        print("执行最终页检查...")

        # 优先检查连续空数据
        if self.empty_counter >= 3:
            print("连续3页无有效数据，确认最终页")
            return True

        # 综合页面元素检查
        confirm_count = 0
        for _ in range(3):
            self.dp.scroll.to_bottom()
            time.sleep(3)

            # 检查终止元素但继续尝试
            has_stop = self.dp.ele('css:p.nothing', timeout=1) or self.dp.ele('css:.compensate-title', timeout=1)
            has_data = self.dp.ele('css:.list-item-target', timeout=1)

            if not has_stop and has_data:
                confirm_count -= 1  # 有数据时降低确认权重
            elif has_stop and not has_data:
                confirm_count += 1

        # 结合数据状态判断
        if confirm_count >= 2 and self.empty_counter >= 2:
            print("综合判断已达最终页")
            return True
        return False

    def run(self):
        try:
            while True:
                print(f'\n{"=" * 30}\n正在采集第 {self.page} 页的数据内容...')

                # 动态加载策略
                if self.page <= 3:
                    success = self._scroll_load()
                else:
                    success = self._button_load()

                if not success:
                    print(f"第 {self.page} 页数据加载失败")

                    if self._check_final_page():
                        print("确认采集完成")
                        break

                    # 自适应等待策略
                    retry_delay = min(15 + self.page * 2, 60)  # 动态增长等待时间
                    print(f"等待{retry_delay}秒后重试...")
                    time.sleep(retry_delay)

                    # 恢复操作
                    self.dp.scroll.to_bottom()
                    time.sleep(2)
                    self.dp.scroll.up(600)
                    time.sleep(2)
                    continue

                self.page += 1
                self.empty_counter = 0  # 重置计数器

        finally:
            self.csv_file.close()
            print("采集完成！")


if __name__ == '__main__':
    scraper = HotelScraper()
    scraper.run()