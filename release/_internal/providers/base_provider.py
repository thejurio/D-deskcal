from abc import ABC, abstractmethod

class BaseCalendarProvider(ABC):
    """
    모든 캘린더 제공자(Provider)가 따라야 하는 기본 클래스(설계도).
    이 클래스를 상속받는 모든 자식 클래스는 아래의 모든 메서드를
    반드시 자신만의 방식으로 구현해야 합니다.
    """

    @abstractmethod
    def get_events(self, start_date, end_date):
        """
        특정 기간 사이의 이벤트 목록을 반환해야 합니다.
        반환값: [ {이벤트 딕셔너리}, {이벤트 딕셔너리}, ... ]
        """
        pass

    @abstractmethod
    def add_event(self, event_data):
        """
        새로운 이벤트를 추가해야 합니다.
        반환값: 생성된 이벤트의 ID 또는 성공 여부(bool)
        """
        pass

    @abstractmethod
    def update_event(self, event_id, event_data):
        """
        기존 이벤트를 수정해야 합니다.
        반환값: 성공 여부(bool)
        """
        pass

    @abstractmethod
    def delete_event(self, event_data, data_manager=None, deletion_mode='all'):
        """
        ... (docstring) ...
        deletion_mode: 'instance', 'future', or 'all'
        """
        pass

    @abstractmethod
    def search_events(self, query):
        """
        주어진 쿼리(검색어)와 일치하는 모든 이벤트를 반환해야 합니다.
        반환값: [ {이벤트 딕셔너리}, ... ]
        """
        pass