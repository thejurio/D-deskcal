# views/layout_calculator.py
import datetime

class MonthLayoutCalculator:
    def __init__(self, events, visible_days, y_offset=25, event_height=20, event_spacing=2):
        self.events = sorted(events, key=lambda e: (e['start'].get('date', e['start'].get('dateTime', ''))[:10]))
        self.visible_days = visible_days
        self.view_start_date = min(visible_days)
        self.view_end_date = max(visible_days)
        
        self.y_offset = y_offset
        self.event_height = event_height
        self.event_spacing = event_spacing

        self.occupied_lanes = {}  # {date: [lane_index, ...]}
        self.event_positions = [] # [{'event': event, 'rect': (x, y, w, h), 'style': '...'}, ...]
        self.more_events = {}     # {date: [event, ...]}

    def calculate(self):
        """모든 이벤트의 위치와 스타일을 계산합니다."""
        if not self.events:
            return

        for event in self.events:
            try:
                self._calculate_event_position(event)
            except Exception as e:
                print(f"이벤트 위치 계산 오류: {e}, 이벤트: {event.get('summary', '')}")
                continue
        
        return self.event_positions, self.more_events

    def _calculate_event_position(self, event):
        start_info, end_info = event['start'], event['end']
        is_all_day = 'date' in start_info
        start_str = start_info.get('date') or start_info.get('dateTime')
        end_str = end_info.get('date') or end_info.get('dateTime')
        
        event_start_date = datetime.date.fromisoformat(start_str[:10])
        event_end_date = datetime.date.fromisoformat(end_str[:10])

        if is_all_day and len(end_str) == 10:
            event_end_date -= datetime.timedelta(days=1)
        elif not is_all_day and end_str.endswith('00:00:00'):
            event_end_date -= datetime.timedelta(days=1)

        draw_start_date = max(event_start_date, self.view_start_date)
        draw_end_date = min(event_end_date, self.view_end_date)

        if draw_start_date > draw_end_date:
            return

        event_span_days = [draw_start_date + datetime.timedelta(d) for d in range((draw_end_date - draw_start_date).days + 1)]
        
        y_level = 0
        while True:
            if not any(y_level in self.occupied_lanes.get(d, []) for d in event_span_days):
                break
            y_level += 1

        # 레이아웃 정보를 저장할 딕셔너리 생성
        position_info = {
            'event': event,
            'y_level': y_level,
            'start_date': event_start_date,
            'end_date': event_end_date,
            'days_in_view': event_span_days
        }
        self.event_positions.append(position_info)

        # 차지하는 레인 정보 업데이트
        for day in event_span_days:
            self.occupied_lanes.setdefault(day, []).append(y_level)


class WeekLayoutCalculator:
    def __init__(self, time_events, all_day_events, start_of_week, hour_height=40):
        self.time_events = sorted(time_events, key=lambda e: e['start'].get('dateTime', ''))
        self.all_day_events = sorted(all_day_events, key=lambda e: (
            datetime.date.fromisoformat(e['start']['date']),
            -(datetime.date.fromisoformat(e['end']['date']) - datetime.date.fromisoformat(e['start']['date'])).days
        ))
        self.start_of_week = start_of_week
        self.hour_height = hour_height

    def calculate_time_events(self, container_width):
        """시간대별 이벤트의 위치와 크기를 계산합니다."""
        positions = []
        events_by_day = {}
        for event in self.time_events:
            start_dt = datetime.datetime.fromisoformat(event['start']['dateTime']).replace(tzinfo=None)
            end_dt = datetime.datetime.fromisoformat(event['end']['dateTime']).replace(tzinfo=None)
            d = start_dt.date()
            while d <= end_dt.date():
                if self.start_of_week <= d < self.start_of_week + datetime.timedelta(days=7):
                    if d not in events_by_day:
                        events_by_day[d] = []
                    events_by_day[d].append(event)
                d += datetime.timedelta(days=1)

        for day_date, day_events in events_by_day.items():
            day_events.sort(key=lambda e: datetime.datetime.fromisoformat(e['start']['dateTime']))
            
            groups = self._group_overlapping_events(day_events)

            day_column_width = container_width / 7
            col_index = (day_date - self.start_of_week).days

            for group in groups:
                num_columns = len(group)
                for i, event in enumerate(group):
                    start_dt = datetime.datetime.fromisoformat(event['start']['dateTime']).replace(tzinfo=None)
                    end_dt = datetime.datetime.fromisoformat(event['end']['dateTime']).replace(tzinfo=None)
                    
                    y = start_dt.hour * self.hour_height + (start_dt.minute / 60) * self.hour_height
                    height = ((end_dt - start_dt).total_seconds() / 3600) * self.hour_height
                    
                    width = day_column_width / num_columns
                    x = col_index * day_column_width + i * width

                    positions.append({'event': event, 'rect': (int(x + 1), int(y), int(width - 2), int(height))})
        
        return positions

    def _group_overlapping_events(self, day_events):
        """겹치는 이벤트를 그룹화합니다."""
        groups = []
        for event in day_events:
            placed = False
            start_dt = datetime.datetime.fromisoformat(event['start']['dateTime'])
            for group in groups:
                last_event_end_dt = datetime.datetime.fromisoformat(group[-1]['end']['dateTime'])
                if start_dt >= last_event_end_dt:
                    group.append(event)
                    placed = True
                    break
            if not placed:
                groups.append([event])
        return groups

    def calculate_all_day_events(self):
        """종일 이벤트의 위치(레인, 시작 컬럼, 스팬)를 계산합니다."""
        positions = []
        lanes_occupancy = [[] for _ in range(7)]
        event_to_lane = {}

        for event in self.all_day_events:
            start_date = datetime.date.fromisoformat(event['start']['date'])
            end_date = datetime.date.fromisoformat(event['end']['date']) - datetime.timedelta(days=1)
            
            event_start_offset = (start_date - self.start_of_week).days
            event_end_offset = (end_date - self.start_of_week).days

            lane_idx = 0
            while True:
                is_free = True
                for day_offset in range(max(0, event_start_offset), min(7, event_end_offset + 1)):
                    if lane_idx in lanes_occupancy[day_offset]:
                        is_free = False
                        break
                if is_free:
                    for day_offset in range(max(0, event_start_offset), min(7, event_end_offset + 1)):
                        lanes_occupancy[day_offset].append(lane_idx)
                    event_to_lane[event['id']] = lane_idx
                    break
                lane_idx += 1
        
        for event in self.all_day_events:
            start_date = datetime.date.fromisoformat(event['start']['date'])
            end_date = datetime.date.fromisoformat(event['end']['date']) - datetime.timedelta(days=1)
            
            draw_start_date = max(start_date, self.start_of_week)
            draw_end_date = min(end_date, self.start_of_week + datetime.timedelta(days=6))

            if draw_start_date > draw_end_date:
                continue

            start_offset = (draw_start_date - self.start_of_week).days
            span = (draw_end_date - draw_start_date).days + 1
            
            if span > 0:
                lane = event_to_lane.get(event['id'], 0)
                positions.append({'event': event, 'lane': lane, 'start_col': start_offset, 'span': span})
        
        num_lanes = max(event_to_lane.values()) + 1 if event_to_lane else 0
        return positions, num_lanes
