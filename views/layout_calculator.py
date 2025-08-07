# views/layout_calculator.py
import datetime
from collections import defaultdict

class MonthLayoutCalculator:
    def __init__(self, events, visible_days, y_offset=25, event_height=20, event_spacing=2):
        self.events = sorted(events, key=lambda e: (e['start'].get('date', e['start'].get('dateTime', ''))[:10]))
        self.visible_days = visible_days
        self.view_start_date = min(visible_days)
        self.view_end_date = max(visible_days)
        
        self.y_offset = y_offset
        self.event_height = event_height
        self.event_spacing = event_spacing

        self.occupied_lanes = {}
        self.event_positions = []
        self.more_events = {}

    def calculate(self):
        if not self.events:
            return [], {}

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
        elif not is_all_day and event_start_date != event_end_date and end_str[11:] == '00:00:00':
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

        position_info = {
            'event': event,
            'y_level': y_level,
            'start_date': event_start_date,
            'end_date': event_end_date,
            'days_in_view': event_span_days
        }
        self.event_positions.append(position_info)

        for day in event_span_days:
            self.occupied_lanes.setdefault(day, []).append(y_level)

class WeekLayoutCalculator:
    def __init__(self, time_events, all_day_events, start_of_week, hour_height=80, hide_weekends=False):
        # [수정] 정렬 기준을 local_dt로 변경
        self.time_events = sorted(time_events, key=lambda e: e['start']['local_dt'])
        self.all_day_events = sorted(all_day_events, key=lambda e: (
            e['start']['local_dt'].date(),
            -(e['end']['local_dt'].date() - e['start']['local_dt'].date()).days
        ))
        self.start_of_week = start_of_week
        self.hour_height = hour_height
        self.hide_weekends = hide_weekends
        self.num_days = 5 if hide_weekends else 7

    def _get_start_dt(self, event):
        return event['start']['local_dt']

    def _get_end_dt(self, event):
        return event['end']['local_dt']

    def _get_day_column_index(self, date_obj):
        if self.hide_weekends:
            if date_obj.weekday() >= 5: return -1
            return date_obj.weekday()
        else:
            return (date_obj - self.start_of_week).days

    def calculate_time_events(self, day_column_width):
        positions = []
        events_by_day = defaultdict(list)
        HORIZONTAL_EVENT_GAP = 2
        GROUP_WIDTH_RATIO = 0.9

        for event in self.time_events:
            start_dt = self._get_start_dt(event)
            events_by_day[start_dt.date()].append(event)
        
        for day_date, day_events in events_by_day.items():
            col_index = self._get_day_column_index(day_date)
            if col_index == -1: continue

            event_groups = self._group_overlapping_events_for_layout(day_events)

            for group in event_groups:
                columns = self._find_columns_in_group(group)
                num_columns = len(columns)
                if num_columns == 0: continue

                group_total_width = day_column_width * GROUP_WIDTH_RATIO
                group_start_x_offset = (day_column_width * (1 - GROUP_WIDTH_RATIO)) / 2
                
                total_gap = (num_columns - 1) * HORIZONTAL_EVENT_GAP
                sub_col_width = (group_total_width - total_gap) / num_columns

                for i, column in enumerate(columns):
                    for event in column:
                        start_dt = self._get_start_dt(event)
                        end_dt = self._get_end_dt(event)
                        
                        y = start_dt.hour * self.hour_height + (start_dt.minute / 60) * self.hour_height
                        duration_seconds = (end_dt - start_dt).total_seconds()
                        height = max(20, (duration_seconds / 3600) * self.hour_height)
                        
                        base_col_x = col_index * day_column_width
                        x_in_group = i * (sub_col_width + HORIZONTAL_EVENT_GAP)
                        x = base_col_x + group_start_x_offset + x_in_group

                        positions.append({'event': event, 'rect': (int(x), int(y), int(sub_col_width), int(height))})
        
        return positions

    def _group_overlapping_events_for_layout(self, day_events):
        if not day_events:
            return []
        
        sorted_events = sorted(day_events, key=self._get_start_dt)
        
        groups = []
        current_group = [sorted_events[0]]
        group_end_time = self._get_end_dt(sorted_events[0])

        for event in sorted_events[1:]:
            event_start_time = self._get_start_dt(event)
            if event_start_time < group_end_time:
                current_group.append(event)
                group_end_time = max(group_end_time, self._get_end_dt(event))
            else:
                groups.append(current_group)
                current_group = [event]
                group_end_time = self._get_end_dt(event)
        
        groups.append(current_group)
        return groups

    def _find_columns_in_group(self, group_events):
        if not group_events:
            return []

        sorted_events = sorted(group_events, key=self._get_start_dt)

        columns = []
        for event in sorted_events:
            placed = False
            event_start_dt = self._get_start_dt(event)
            for column in columns:
                last_event_in_column = column[-1]
                last_event_end_dt = self._get_end_dt(last_event_in_column)
                
                if event_start_dt >= last_event_end_dt:
                    column.append(event)
                    placed = True
                    break
            if not placed:
                columns.append([event])
                
        return columns

    def calculate_all_day_events(self):
        positions = []
        lanes_occupancy = [[] for _ in range(self.num_days)]
        event_to_lane = {}

        for event in self.all_day_events:
            start_date = self._get_start_dt(event).date()
            end_date = self._get_end_dt(event).date()
            
            # 종일 이벤트 보정
            if 'date' in event['start']:
                end_date -= datetime.timedelta(days=1)
            elif start_date != end_date and self._get_end_dt(event).time() == datetime.time(0, 0):
                end_date -= datetime.timedelta(days=1)

            view_end_date = self.start_of_week + datetime.timedelta(days=self.num_days - 1)
            draw_start_date = max(start_date, self.start_of_week)
            draw_end_date = min(end_date, view_end_date)

            if draw_start_date > draw_end_date:
                continue

            lane_idx = 0
            while True:
                is_free = True
                
                current_date_in_view = draw_start_date
                while current_date_in_view <= draw_end_date:
                    col_idx = self._get_day_column_index(current_date_in_view)
                    if col_idx != -1 and lane_idx in lanes_occupancy[col_idx]:
                        is_free = False
                        break
                    current_date_in_view += datetime.timedelta(days=1)

                if is_free:
                    current_date_in_view = draw_start_date
                    while current_date_in_view <= draw_end_date:
                        col_idx = self._get_day_column_index(current_date_in_view)
                        if col_idx != -1:
                            lanes_occupancy[col_idx].append(lane_idx)
                        current_date_in_view += datetime.timedelta(days=1)
                    event_to_lane[event['id']] = lane_idx
                    break
                lane_idx += 1
        
        for event in self.all_day_events:
            start_date = self._get_start_dt(event).date()
            end_date = self._get_end_dt(event).date()
            
            if 'date' in event['start']:
                end_date -= datetime.timedelta(days=1)
            elif start_date != end_date and self._get_end_dt(event).time() == datetime.time(0, 0):
                end_date -= datetime.timedelta(days=1)

            view_end_date = self.start_of_week + datetime.timedelta(days=self.num_days - 1)
            draw_start_date = max(start_date, self.start_of_week)
            draw_end_date = min(end_date, view_end_date)

            if draw_start_date > draw_end_date:
                continue

            start_col = self._get_day_column_index(draw_start_date)
            end_col = self._get_day_column_index(draw_end_date)
            
            if start_col == -1 or end_col == -1: continue

            span = end_col - start_col + 1
            
            if span > 0:
                lane = event_to_lane.get(event['id'], 0)
                positions.append({'event': event, 'lane': lane, 'start_col': start_col, 'span': span})
        
        num_lanes = max(event_to_lane.values()) + 1 if event_to_lane else 0
        return positions, num_lanes