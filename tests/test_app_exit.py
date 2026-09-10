import queue

from app import FinancialExtractorApp


class FakeRoot:
    def __init__(self):
        self.quit_calls = 0
        self.destroy_calls = 0
        self.after_calls = 0

    def quit(self):
        self.quit_calls += 1

    def destroy(self):
        self.destroy_calls += 1

    def after(self, *_args):
        self.after_calls += 1


class FakeProgress:
    def __init__(self):
        self.stop_calls = 0

    def stop(self):
        self.stop_calls += 1


class ActiveWorker:
    @staticmethod
    def is_alive():
        return True


def test_exit_closes_root_with_active_worker():
    app = FinancialExtractorApp.__new__(FinancialExtractorApp)
    app.root = FakeRoot()
    app.progress = FakeProgress()
    app.worker = ActiveWorker()
    app.closing = False

    app._on_close()
    app._on_close()

    assert app.closing is True
    assert app.progress.stop_calls == 1
    assert app.root.quit_calls == 1
    assert app.root.destroy_calls == 1


def test_queue_poller_does_not_reschedule_while_closing():
    app = FinancialExtractorApp.__new__(FinancialExtractorApp)
    app.root = FakeRoot()
    app.work_queue = queue.Queue()
    app.closing = True

    app._poll_queue()

    assert app.root.after_calls == 0
