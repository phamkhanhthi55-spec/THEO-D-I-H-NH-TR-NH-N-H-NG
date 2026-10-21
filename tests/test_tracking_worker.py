"""
Test tracking worker preserving existing status when carrier returns unchanged or no milestone.
"""

import unittest
from unittest.mock import patch, MagicMock
from src.tracking import TrackingResult
from src.main_window import TrackingWorker


class TestTrackingWorkerUnchangedStatus(unittest.TestCase):
    """Kiểm tra TrackingWorker xử lý trạng thái dậm chân tại chỗ."""

    @patch('src.tracking.track_order')
    def test_worker_preserves_existing_status_on_no_change_or_failure(self, mock_track):
        """Khi đơn hàng đã có trạng thái cũ và lần tra cứu này không có mốc mới hoặc lỗi web,
        worker vẫn ghi nhận thành công và giữ nguyên trạng thái cũ."""
        # Giả lập track_order trả về thất bại (ví dụ: web không có mốc mới / timeout)
        mock_track.return_value = TrackingResult(success=False, error="Không tìm thấy hành trình")

        orders = [
            (1, "SPXVN06960122507A", "SPX", "", "Đơn hàng đã đến kho Hung Yen SOC", "22:20:14 17 Oct: Đơn hàng đã đến kho Hung Yen SOC")
        ]

        worker = TrackingWorker(orders)
        results = []
        finished_stats = []

        worker.result.connect(lambda oid, success, status, detail, err: results.append((oid, success, status, detail, err)))
        worker.finished_all.connect(lambda succ, fail: finished_stats.append((succ, fail)))

        worker.run()

        # Phải được tính là thành công
        self.assertEqual(len(results), 1)
        oid, success, status, detail, err = results[0]
        self.assertTrue(success)
        self.assertEqual(status, "Đơn hàng đã đến kho Hung Yen SOC")
        self.assertEqual(err, "")

        self.assertEqual(len(finished_stats), 1)
        succ_count, fail_count = finished_stats[0]
        self.assertEqual(succ_count, 1)
        self.assertEqual(fail_count, 0)

    @patch('src.tracking.track_order')
    def test_worker_reports_failure_for_new_order_without_existing_status(self, mock_track):
        """Khi đơn hàng chưa từng có hành trình mà tra cứu thất bại thì mới báo lỗi."""
        mock_track.return_value = TrackingResult(success=False, error="Không tìm thấy mã vận đơn")

        orders = [
            (2, "INVALID12345", "SPX", "", "", "")
        ]

        worker = TrackingWorker(orders)
        results = []
        finished_stats = []

        worker.result.connect(lambda oid, success, status, detail, err: results.append((oid, success, status, detail, err)))
        worker.finished_all.connect(lambda succ, fail: finished_stats.append((succ, fail)))

        worker.run()

        self.assertEqual(len(results), 1)
        oid, success, status, detail, err = results[0]
        self.assertFalse(success)
        self.assertEqual(err, "Không tìm thấy mã vận đơn")

        succ_count, fail_count = finished_stats[0]
        self.assertEqual(succ_count, 0)
        self.assertEqual(fail_count, 1)


if __name__ == '__main__':
    unittest.main()
