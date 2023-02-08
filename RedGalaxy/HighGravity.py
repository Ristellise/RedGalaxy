import logging
import re

from . import global_instance, SessionManager
from bs4 import BeautifulSoup
import js2py


class HighGravity:
    magic = "a"

    def __init__(self, sessionInstance: SessionManager = None):
        """
        HighGravity loads twitter's JS files and extracts graphql routes to ensure
        that the routeIds used are the latest ones for the routes required by the rest of the
        other params.
        :param sessionInstance:
        """
        if sessionInstance is None:
            sessionInstance = global_instance
        self.session = sessionInstance
        self.logging = logging.getLogger("HighGravity")

    async def retrieve_routes(self):
        """
        Requests and retireves the routes.
        :return: A dictionary mapped by the route names.
        """
        self.session.do_headers("https://twitter.com", set_auth=False)
        r = await self.session.get("https://twitter.com")
        if r.status != 200:
            print(r.status)
            return {}

        soup = BeautifulSoup(await r.text(), "lxml")
        r = re.compile("\"(.*?)\":\"(.*?)\"")
        ra = re.compile(",(.*?):\"(.*?)\"")
        r2 = re.compile("\"https://abs.twimg.com/(.*?)/\"")
        # print(soup)
        rba_f = None
        routes = {}
        for script in soup.select("script"):
            if "endpoints" in script.text.lower():
                rba = r2.findall(script.text)
                if len(rba) == 1:
                    rba_f = rba[0]
                rb = r.findall(script.text)
                rab = ra.findall(script.text)
                for i in rab:
                    if i[0] == "api" and len(i[1]) == 7:
                        ra = await self.process_js("https://abs.twimg.com/", rba_f, i[0], i[1])
                        if ra is None:
                            continue
                        for route_key, route_data in ra.items():
                            routes[route_key] = route_data
                for match in rb:
                    java, hash_ver = match
                    if "endpoints" in java.lower():
                        # print(match)
                        if rba_f is None:
                            continue
                        ra = await self.process_js("https://abs.twimg.com/", rba_f, match[0], match[1])
                        if ra is None:
                            continue
                        for route_key, route_data in ra.items():
                            routes[route_key] = route_data
                # print(rb)
        return routes

    filtered = [
        "AudioSpaces",
        "UsersGraphQL",
        "api"
    ]

    async def process_js(self, root, mode, route, hash):
        process = False
        js_url = f"{root}{mode}/{route}.{hash}{self.magic}.js"
        self.logging.debug(f"Processing JS: {js_url}")
        #print(js_url)
        for filt in self.filtered:
            if route.endswith(filt):
                process = True
                break
        if not process:
            return
        self.logging.debug(f"Retrieving JS content: {js_url}")
        j = await self.session.get(js_url)
        if j.status == 200:
            js = await j.text()
            reg = re.compile("({)e\.exports=({+.+?}+)")  # Bit cursed but eh.
            routes = [f"{a}{b}" for a, b in reg.findall(js)]
            final_routes = {}
            for route in routes:
                # print(route[1:-1])
                c = js2py.eval_js(f"route = {route[1:-1]}")
                #print(type(c), c)
                if isinstance(c, js2py.base.JsObjectWrapper):
                    url = f"https://api.twitter.com/graphql/{c['queryId']}/{c['operationName']}"
                    features = c['metadata']
                    final_routes[c['operationName']] = [url, features]
                else:
                    raise Exception(f"Export string changed or invalid?")
            return final_routes
