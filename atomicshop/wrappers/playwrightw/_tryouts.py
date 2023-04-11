# Tryouts:
"""
# Regular function for 'time.sleep(10)'.
self.playwright.page.wait_for_timeout(10000)
"""


"""
# Subscribe to 'request' event and wait for the request with the specified URL.
# Anything that matches the URL pattern will be intercepted: *test.php?get=test*.
with self.playwright.page.expect_request("**/*test.php?get=test*") as request_info:
    print(request_info.value.url)
"""


"""
# Handler function for each 'response' event. Should work in parallel, but has some conditions that I currently can't
# figure out.
def response_handler(response):
    print(">>", response.request.method, response.request.url)


# Subscribe to 'response' event, which will trigger 'response_handler' function.
self.playwright.page.on("response", response_handler)
# Unsubscribe from 'response' event.
self.playwright.page.remove_listener("response", response_handler)
"""


"""
# Another way to subscribe to event. This one is for any URL.
test = self.playwright.page.expect_response("**/*")

# When hit it will contain value, though it is private, so it is for reference only.
print(test._event.value)
"""


"""
# Another way of subscription is using route, didn't have time for testing.

# Usage1. Using lambda function.
self.playwright.page.route("**/*example.com*", lambda route: route.fulfill(status=200, body=""))


# Usage2. Using handler function.
def route_handler(route):
    print(">>", route.request.method, route.request.url)
    route.fulfill(status=200, body="")
    # route.continue_()

self.playwright.page.route("**/*", route_handler)
"""


"""
# This one by copilot, didn't test it.
class WaitForNetworkIdleRequestBased:
    def __init__(self, page, timeout=30, max_inflight_requests=0):
        self.page = page
        self.timeout = timeout
        self.max_inflight_requests = max_inflight_requests
        self.inflight_requests = 0
        self.continue_waiting = None
        self.timer = None

    def wait_for_network_idle(self):
        self.inflight_requests = 0
        self.continue_waiting = True
        self.page.on("request", self.on_request)
        self.page.on("requestfinished", self.on_requestfinished)
        self.page.on("requestfailed", self.on_requestfinished)
        self.timer = threading.Timer(self.timeout, self.on_timeout)
        self.timer.start()
        while self.continue_waiting:
            time.sleep(0.1)
        self.page.off("request", self.on_request)
        self.page.off("requestfinished", self.on_requestfinished)
        self.page.off("requestfailed", self.on_requestfinished)

    def on_request(self, request):
        self.inflight_requests += 1

    def on_requestfinished(self, request):
        self.inflight_requests -= 1
        if self.inflight_requests <= self.max_inflight_requests:
            self.continue_waiting = False
            self.timer.cancel()

    def on_timeout(self):
        self.continue_waiting = False
"""


"""
# This one the improved version of the above, but for 'response' instead of 'request'.
# For some reason this is working only for several first responses, and then it stops working.
# So, no reason to use it.
class WaitForNetworkIdle:
    def __init__(self, page, timeout=1, reference=None, args=None):
        self.page = page
        self.timeout = timeout
        self.reference = reference
        self.args = args
        self.continue_waiting = None
        self.timer = Timer()
        self.response_counter = 0

    def wait_for_network_idle(self):
        self.continue_waiting = True
        self.page.on("response", self.on_response)
        # self.page.on("request", self.on_request)
        # self.page.on("requestfinished", self.on_requestfinished)
        # self.page.on("requestfailed", self.on_requestfinished)
        # self.timer = threading.Timer(self.timeout, self.on_timeout)
        self.timer.start()
        self.reference(*self.args)
        waits.maximum_idle(self.page)
        while self.timer.measure() < self.timeout:
            print(self.timer.measure())
            time.sleep(0.1)

        self.page.remove_listener("response", self.on_response)
        self.timer.stop()

    def on_response(self, response):
        print(">>", response.request.method, response.request.url)
        self.response_counter += 1
        # time.sleep(1)
        self.timer.restart()

    def on_requestfinished(self, request):
        print(">>", request.method, request.url)
        self.response_counter += 1
        self.timer.restart()
        

# Usage1.
WaitForNetworkIdle(
    self.playwright.page,
    reference=self.playwright.refresh_page).wait_for_network_idle()
    
    
# Usage2.
WaitForNetworkIdle(
    self.playwright.page,
    reference=self.playwright.page.goto,
    args=(self.config['url'],)).wait_for_network_idle()
"""