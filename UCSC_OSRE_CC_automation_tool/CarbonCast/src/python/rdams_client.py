#!/usr/bin/env python
"""List dataset metadata, subset data subset requests,
check on request status.

Usage:
```
rdams-client.py -get_summary <dsnnn.n>
rdams-client.py -get_metadata <dsnnn.n> <-f>
rdams-client.py -get_param_summary <dsnnn.n> <-f>
rdams-client.py -submit [control_file_name]
rdams-client.py -get_status <RequestIndex> <-proc_status>
rdams-client.py -download [RequestIndex]
rdams-client.py -globus_download [RequestIndex]
rdams-client.py -get_control_file_template <dsnnn.n>
rdams-client.py -help
```
"""
__version__ = '3.0.0'
__author__ = 'Doug Schuster (schuster@ucar.edu), Riley Conroy (rpconroy@ucar.edu)'

import sys
import os
import requests
import getpass
import json
import argparse
import codecs
import pdb
import time
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

# Import rate limiting components if available
try:
    from automation.rate_limiter import RateLimiter, RateLimitConfig, create_rate_limiter
    from automation.error_handler import ErrorHandler, ErrorHandlingConfig, create_error_handler
    from automation.request_throttler import RequestThrottler, ThrottlingConfig, create_request_throttler
    RATE_LIMITING_AVAILABLE = True
except ImportError:
    RATE_LIMITING_AVAILABLE = False
    print("Rate limiting components not available - running in basic mode")


# NCAR migrated the RDA API host from rda.ucar.edu to gdex.ucar.edu
# (old host 301-redirects; POST bodies don't survive the redirect).
BASE_URL = 'https://gdex.ucar.edu/api/'
DEFAULT_AUTH_FILE = './rdams_token.txt'

# Python 2 compatibility
try:
    input = raw_input
except NameError:
    pass


class RateLimitedRDAMSClient:
    """
    Rate-limited RDAMS client that integrates with the comprehensive rate limiting system.
    
    This client provides intelligent request management, error handling, and throttling
    for all RDAMS API interactions to ensure compliance with API limits and maximize
    efficiency.
    """
    
    def __init__(self,
                 enable_rate_limiting: bool = True,
                 enable_error_handling: bool = True,
                 enable_request_throttling: bool = True,
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize the rate-limited RDAMS client.
        
        Args:
            enable_rate_limiting: Enable intelligent rate limiting
            enable_error_handling: Enable comprehensive error handling
            enable_request_throttling: Enable request throttling and queuing
            config: Optional configuration dictionary
        """
        self.logger = self._setup_logging()
        self.config = config or self._get_default_config()
        
        # Initialize rate limiting components if available
        self.rate_limiter = None
        self.error_handler = None
        self.request_throttler = None
        
        if RATE_LIMITING_AVAILABLE:
            if enable_rate_limiting:
                self.rate_limiter = self._create_rate_limiter()
            
            if enable_error_handling:
                self.error_handler = self._create_error_handler()
            
            if enable_request_throttling:
                self.request_throttler = self._create_request_throttler()
            
            # Set up integrations
            self._setup_integrations()
        
        self.logger.info(f"RateLimitedRDAMSClient initialized (rate_limiting={enable_rate_limiting})")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for the RDAMS client."""
        logger = logging.getLogger('rdams_client.rate_limited')
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        
        return logger
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for rate-limited client."""
        return {
            "requests_per_minute": 10,
            "requests_per_hour": 600,
            "adaptive_rate_limiting": True,
            "circuit_breaker_enabled": True,
            "max_retries": 3,
            "base_retry_delay": 60.0,
            "max_retry_delay": 1800.0,
            "request_timeout": 300.0,
            "throttling_enabled": True,
            "max_queue_size": 100
        }
    
    def _create_rate_limiter(self) -> RateLimiter:
        """Create rate limiter for RDAMS API."""
        rate_config = RateLimitConfig(
            requests_per_minute=self.config["requests_per_minute"],
            requests_per_hour=self.config["requests_per_hour"],
            adaptive_enabled=self.config["adaptive_rate_limiting"],
            circuit_breaker_enabled=self.config["circuit_breaker_enabled"],
            failure_threshold=5,
            recovery_timeout_seconds=300
        )
        return create_rate_limiter(rate_config)
    
    def _create_error_handler(self) -> ErrorHandler:
        """Create error handler for RDAMS API."""
        error_config = ErrorHandlingConfig(
            default_max_retries=self.config["max_retries"],
            rate_limit_base_delay=self.config["base_retry_delay"],
            rate_limit_max_delay=self.config["max_retry_delay"],
            circuit_breaker_enabled=self.config["circuit_breaker_enabled"],
            graceful_degradation_enabled=True,
            pattern_recognition_enabled=True
        )
        return create_error_handler(error_config)
    
    def _create_request_throttler(self) -> RequestThrottler:
        """Create request throttler for RDAMS API."""
        throttle_config = ThrottlingConfig(
            max_queue_size=self.config["max_queue_size"],
            max_concurrent_requests=3,  # Conservative for RDAMS
            default_timeout_seconds=self.config["request_timeout"],
            adaptive_throttling=True,
            rate_limiter_integration=True,
            error_handler_integration=True,
            min_request_interval_seconds=6.0,  # 10 req/min = 6s interval
            max_request_interval_seconds=60.0
        )
        return create_request_throttler(throttle_config)
    
    def _setup_integrations(self):
        """Set up integrations between rate limiting components."""
        if self.error_handler and self.rate_limiter:
            self.error_handler.set_integrations(rate_limiter=self.rate_limiter)
        
        if self.request_throttler and (self.rate_limiter or self.error_handler):
            self.request_throttler.set_integrations(
                rate_limiter=self.rate_limiter,
                error_handler=self.error_handler
            )
        
        if self.request_throttler:
            self.request_throttler.start()
    
    def make_request(self,
                    method: str,
                    url: str,
                    **kwargs) -> requests.Response:
        """
        Make a rate-limited request to the RDAMS API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            **kwargs: Additional arguments for requests
            
        Returns:
            Response object
            
        Raises:
            Exception: If request fails after all retries
        """
        if not RATE_LIMITING_AVAILABLE or not self.rate_limiter:
            # Fallback to direct request
            return self._make_direct_request(method, url, **kwargs)
        
        # Check rate limits
        can_request, wait_time = self.rate_limiter.can_make_request()
        if not can_request:
            self.logger.warning(f"Rate limit hit, waiting {wait_time:.1f}s")
            time.sleep(wait_time)
        
        # Acquire rate limiter slot
        if not self.rate_limiter.acquire_request_slot():
            raise Exception("Unable to acquire rate limiter slot")
        
        try:
            start_time = time.time()
            response = self._make_direct_request(method, url, **kwargs)
            end_time = time.time()
            
            # Record successful request
            self.rate_limiter.record_request_result(
                success=True,
                response_time=end_time - start_time,
                status_code=response.status_code
            )
            
            return response
            
        except Exception as e:
            # Record failed request
            status_code = getattr(e, 'response', {}).get('status_code', 500)
            self.rate_limiter.record_request_result(
                success=False,
                response_time=time.time() - start_time if 'start_time' in locals() else 0,
                status_code=status_code,
                error_type=type(e).__name__
            )
            
            # Handle error with error handler
            if self.error_handler:
                action, params = self.error_handler.handle_error(
                    e,
                    context={
                        'method': method,
                        'url': url,
                        'status_code': status_code
                    }
                )
                
                if action.name == 'RETRY' and params.get('delay', 0) > 0:
                    self.logger.info(f"Retrying request after {params['delay']:.1f}s")
                    time.sleep(params['delay'])
                    return self.make_request(method, url, **kwargs)
            
            raise e
    
    def _make_direct_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Make a direct request without rate limiting."""
        method = method.upper()
        
        if method == 'GET':
            response = requests.get(url, **kwargs)
        elif method == 'POST':
            response = requests.post(url, **kwargs)
        elif method == 'DELETE':
            response = requests.delete(url, **kwargs)
        elif method == 'PUT':
            response = requests.put(url, **kwargs)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        # Check for rate limit responses
        if response.status_code == 429:
            retry_after = response.headers.get('Retry-After', '60')
            try:
                wait_time = float(retry_after)
            except ValueError:
                wait_time = 60.0
            
            raise requests.exceptions.HTTPError(
                f"429 Too Many Requests - Retry after {wait_time}s",
                response=response
            )
        
        # Raise for other HTTP errors
        response.raise_for_status()
        return response
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of rate limiting components."""
        status = {
            "rate_limiting_available": RATE_LIMITING_AVAILABLE,
            "components": {
                "rate_limiter": self.rate_limiter is not None,
                "error_handler": self.error_handler is not None,
                "request_throttler": self.request_throttler is not None
            }
        }
        
        if self.rate_limiter:
            status["rate_limiter_status"] = self.rate_limiter.get_status().__dict__
        
        if self.error_handler:
            status["error_statistics"] = self.error_handler.get_error_statistics()
        
        if self.request_throttler:
            status["throttler_metrics"] = self.request_throttler.get_metrics()
        
        return status
    
    def cleanup(self):
        """Clean up rate limiting components."""
        if self.request_throttler:
            self.request_throttler.stop()
        
        self.logger.info("RateLimitedRDAMSClient cleaned up")


# Global rate-limited client instance
_rate_limited_client: Optional[RateLimitedRDAMSClient] = None


def get_rate_limited_client() -> RateLimitedRDAMSClient:
    """Get or create the global rate-limited client instance."""
    global _rate_limited_client
    
    if _rate_limited_client is None:
        _rate_limited_client = RateLimitedRDAMSClient()
    
    return _rate_limited_client


def enable_rate_limiting(enable: bool = True):
    """Enable or disable rate limiting for all RDAMS requests."""
    global _rate_limited_client
    
    if enable and RATE_LIMITING_AVAILABLE:
        _rate_limited_client = RateLimitedRDAMSClient(
            enable_rate_limiting=True,
            enable_error_handling=True,
            enable_request_throttling=True
        )
        print("✅ Rate limiting enabled for RDAMS client")
    else:
        _rate_limited_client = None
        print("❌ Rate limiting disabled for RDAMS client")

def query(args=None):
    """Perform a query based on command line like arguments.

    Args:
        args (list): argument list of querying commands.

    Returns:
        (dict): Output of json decoded API query.

    Example:
        ```
        >>> query(['-get_status', '123456'])

        >>> query(['-get_metadata', 'ds083.2'])
        ```
    """
    parser = get_parser()
    if args is None or len(args) == 0:
        parser.parse_args(['-h'])
    args = parser.parse_args(args)
    args_dict = args.__dict__
    func,params = get_selected_function(args_dict)
    if args_dict['outdir'] and func==download:
        out_dir = args_dict['outdir']
        return func(params, out_dir)
    result = func(params)
    if not args.noprint:
        print(json.dumps(result, indent=3))
    return result

def add_ds_str(ds_num):
    """Adds 'ds' to ds_num if needed.
    Throws error if ds number isn't valid.
    """
    ds_num = ds_num.strip()
    if ds_num[0:2] != 'ds':
        ds_num = 'ds' + ds_num
    if len(ds_num) != 7:
        print("'" + ds_num + "' is not valid.")
        sys.exit()
    return ds_num

def get_userinfo():
    """Get token from command line."""
    print('Please visit https://rda.ucar.edu/accounts/profile/ to access token.')
    token = input("Paste that token here: ")
    write_token_file(token)
    return token

def write_token_file(token, token_file=DEFAULT_AUTH_FILE):
    """Write token to a file."""
    with open(token_file, "w") as fo:
        fo.write(token)

def read_token_file(token_file):
    """Read user information from token file.

    Args:
        token_file (str): location of token file.

    Returns:
        (str): token
    """
    with open(token_file, 'r') as f:
        token = f.read()
    return token.strip()

def read_control_file(control_file):
    """Reads control file, and return python dict.

    Args:
        control_file (str): Location of control file to parse.
                Or control file string.

    Returns:
        (dict) python dict representing control file.
    """
    control_params = {}
    if os.path.exists(control_file):
        myfile = open(control_file, 'r')
    else:
        myfile = control_file.split('\n')

    for line in myfile:
        line = line.strip()
        if line.startswith('#') or line == "":
            continue
        li = line.rstrip()
        # maxsplit=1: values (e.g. date ranges, params) may contain '=' and
        # a 2-way unpack of a 3-element split raises ValueError
        (key, value) = li.split('=', 1)
        control_params[key] = value

    # Handle empty params
    if 'param' in control_params and control_params['param'].strip() == '':
        all_params = get_all_params(control_params['dataset'])
        control_params['param'] = '/'.join(all_params)

    try:
        myfile.close()
    except:
        pass
    return control_params

def get_parser():
    """Creates and returns parser object.

    Returns:
        (argparse.ArgumentParser): Parser object from which to parse arguments.
    """
    description = "Queries NCAR RDA REST API."
    parser = argparse.ArgumentParser(prog='rdams', description=description)
    parser.add_argument('-noprint', '-np',
            action='store_true',
            required=False,
            help="Do not print result of queries.")
    parser.add_argument('-outdir', '-od',
            nargs='?',
            required=False,
            help="Change the output directory of downloaded files")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-get_summary', '-gsum',
            type=str,
            metavar='<dsid>',
            required=False,
            help="Get a summary of the given dataset.")
    group.add_argument('-get_metadata', '-gm',
            type=str,
            metavar='<dsid>',
            required=False,
            help="Get metadata for a given dataset.")
    group.add_argument('-get_param_summary', '-gpm',
            type=str,
            metavar='<dsid>',
            required=False,
            help="Get only parameters for a given dataset.")
    group.add_argument('-submit', '-s',
            type=str,
            metavar='<control file>',
            required=False,
            help="Submit a request using a control file.")
    group.add_argument('-get_status', '-gs',
            type=str,
            nargs='?',
            const='ALL',
            metavar='<Request Index>',
            required=False,
            help="Get a summary of the given dataset.")
    group.add_argument('-download', '-d',
            type=str,
            required=False,
            metavar='<Request Index>',
            help="Download data given a request id.")
    group.add_argument('-get_filelist', '-gf',
            type=str,
            required=False,
            metavar='<Request Index>',
            help="Query the filelist for a completed request.")
    group.add_argument('-globus_download', '-gd',
            type=str,
            required=False,
            metavar='<Request Index>',
            help="Start a globus transfer for a give request index.")
    group.add_argument('-get_control_file_template', '-gt',
            type=str,
            metavar='<dsid>',
            required=False,
            help="Get a template control file used for subsetting.")
    group.add_argument('-purge', # Sorry no -p
            type=str,
            metavar='<Request Index>',
            required=False,
            help="Purge a request.")
    return parser

def check_status(ret, token_file=DEFAULT_AUTH_FILE):
    """Checks that status of return object.

    Exits if a 401 status code.

    Args:
        ret (response.Response): Response of a request.
        token_file (str) : password file. Will remove if auth incorrect

    Returns:
        None
    """
    if ret.status_code == 401: # Not Authorized
        print(ret.content)
        exit(1)

def check_file_status(filepath, filesize):
    """Prints file download status as percent of file complete.

    Args:
        filepath (str): File being downloaded.
        filesize (int): Expected total size of file in bytes.

    Returns:
        None
    """
    sys.stdout.write('\r')
    sys.stdout.flush()
    size = int(os.stat(filepath).st_size)
    percent_complete = (size/filesize)*100
    sys.stdout.write('%.3f %s' % (percent_complete, '% Completed'))
    sys.stdout.flush()

def download_files(filelist, out_dir='./', cookie_file=None):
    """Download files in a list.

    Args:
        filelist (list): List of web files to download.
        out_dir (str): directory to put downloaded files

    Returns:
        (list): files that were fully downloaded. Failed downloads are
                logged and skipped; partial files are removed.
    """
    downloaded = []
    for _file in filelist:
        file_base = os.path.basename(_file)
        out_file = os.path.join(out_dir, file_base)
        print('Downloading', file_base)
        # temp name so an interrupted download never masquerades as complete
        tmp_file = out_file + '.part'
        try:
            header = requests.head(_file, allow_redirects=True, stream=True,
                                   timeout=(30, 120))
            header.raise_for_status()
            filesize = int(header.headers.get('Content-Length') or 0)
            req = requests.get(_file, allow_redirects=True, stream=True,
                               timeout=(30, 300))
            req.raise_for_status()
            with open(tmp_file, 'wb') as outfile:
                chunk_size = 1048576
                for chunk in req.iter_content(chunk_size=chunk_size):
                    outfile.write(chunk)
                    if filesize and chunk_size < filesize:
                        check_file_status(tmp_file, filesize)
            actual_size = os.stat(tmp_file).st_size
            if filesize and actual_size != filesize:
                raise IOError(
                    f'Incomplete download: got {actual_size} of {filesize} bytes')
            os.replace(tmp_file, out_file)
            if filesize:
                check_file_status(out_file, filesize)
            downloaded.append(out_file)
            print()
        except Exception as e:
            print(f'Failed to download {file_base}: {e}')
            try:
                if os.path.exists(tmp_file):
                    os.remove(tmp_file)
            except OSError:
                pass
    return downloaded

def encode_url(url, token):
    return url + '?token=' + token

def get_authentication(token_file=DEFAULT_AUTH_FILE):
    """Attempts to get authentication.

    Args:
        token_file (str): location of password file.

    Returns:
        (tuple): token
    """
    if os.path.isfile(token_file) and os.path.getsize(token_file) > 0:
        return read_token_file(token_file)
    else:
        return get_userinfo()


def get_summary(ds):
    """Returns summary of dataset with rate limiting.

    Args:
        ds (str): Datset id. e.g. 'ds083.2'

    Returns:
        dict: JSON decoded result of the query.
    """
    url = BASE_URL + 'summary/'
    url += ds

    token = get_authentication()
    
    # Use rate-limited client if available
    client = get_rate_limited_client()
    if client and RATE_LIMITING_AVAILABLE:
        try:
            ret = client.make_request('GET', encode_url(url, token))
            check_status(ret)
            return ret.json()
        except Exception as e:
            # Fallback to direct request
            print(f"Rate-limited request failed, falling back: {e}")
    
    # Fallback to original implementation
    ret = requests.get(encode_url(url,token))
    check_status(ret)
    return ret.json()

def get_metadata(ds):
    """Return metadata of dataset with rate limiting.

    Args:
        ds (str): Datset id. e.g. 'ds083.2'

    Returns:
        dict: JSON decoded result of the query.
    """
    url = BASE_URL + 'metadata/'
    url += ds

    token = get_authentication()
    
    # Use rate-limited client if available
    client = get_rate_limited_client()
    if client and RATE_LIMITING_AVAILABLE:
        try:
            ret = client.make_request('GET', encode_url(url, token))
            check_status(ret)
            return ret.json()
        except Exception as e:
            print(f"Rate-limited request failed, falling back: {e}")
    
    # Fallback to original implementation
    ret = requests.get(encode_url(url,token))
    check_status(ret)
    return ret.json()

def get_all_params(ds):
    """Return set of parameters for a dataset.

    Args:
        ds (str): Datset id. e.g. 'ds083.2'

    Returns:
        set: All unique params in dataset.
    """
    res = get_param_summary(ds)
    res_data = res['data']['data']
    param_names = set()
    for param in res_data:
        param_names.add(param['param'])
    return param_names


def get_param_summary(ds):
    """Return summary of parameters for a dataset with rate limiting.

    Args:
        ds (str): Datset id. e.g. 'ds083.2'

    Returns:
        dict: JSON decoded result of the query.
    """
    url = BASE_URL + 'paramsummary/'
    url += ds

    token = get_authentication()
    
    # Use rate-limited client if available
    client = get_rate_limited_client()
    if client and RATE_LIMITING_AVAILABLE:
        try:
            ret = client.make_request('GET', encode_url(url, token))
            check_status(ret)
            return ret.json()
        except Exception as e:
            print(f"Rate-limited request failed, falling back: {e}")
    
    # Fallback to original implementation
    ret = requests.get(encode_url(url,token))
    check_status(ret)
    return ret.json()


def submit_json(json_file):
    """Submit a RDA subset or format conversion request using json file or dict.

    Args:
        json_file (str): json control file to submit.
                OR
                Python dict to submit.

    Returns:
        dict: JSON decoded result of the query.
    """
    if type(json_file) is str:
        assert os.path.isfile(json_file)
        with open(json_file) as fh:
            control_dict = json.load(fh)
    else:
        assert type(json_file) is dict
        control_dict = json_file

    url = BASE_URL + 'submit/'

    token = get_authentication()
    ret = requests.post(encode_url(url,token), json=control_dict)

    print("HTTP status code:", ret.status_code)
    print("Raw response content:", ret.content)
    try:
        return ret.json()
    except Exception as e:
        print("Failed to decode JSON:", e)
        return {"http_response": ret.status_code, "content": ret.content.decode(errors="replace")}

def submit(control_file_name):
    """Submit a RDA subset or format conversion request.
    Calls submit json after reading control_file

    Args:
        control_file_name (str): control file to submit.

    Returns:
        dict: JSON decoded result of the query.
    """
    _dict = read_control_file(control_file_name)
    return submit_json(_dict)


def get_status(request_idx=None):
    """Get status of request with rate limiting.
    If request_ix not provided, get all open requests

    Args:
        request_idx (str, Optional): Request Index, typcally a 6-digit integer.

    Returns:
        dict: JSON decoded result of the query.
    """
    if request_idx is None:
        request_idx = 'ALL'
    url = BASE_URL + 'status/'
    url += str(request_idx)

    token = get_authentication()
    
    # Use rate-limited client if available
    client = get_rate_limited_client()
    if client and RATE_LIMITING_AVAILABLE:
        try:
            ret = client.make_request('GET', encode_url(url, token))
            check_status(ret)
            return ret.json()
        except Exception as e:
            print(f"Rate-limited request failed, falling back: {e}")
    
    # Fallback to original implementation
    ret = requests.get(encode_url(url,token))
    check_status(ret)
    return ret.json()

def get_filelist(request_idx):
    """Gets filelist for request

    Args:
        request_idx (str): Request Index, typically a 6-digit integer.

    Returns:
        dict: JSON decoded result of the query.
    """
    url = BASE_URL + 'get_req_files/'
    url += str(request_idx)

    token = get_authentication()
    ret = requests.get(encode_url(url,token))

    check_status(ret)

    return ret.json()


def download(request_idx, out_dir='./'):
    """Download files given request Index

    Args:
        request_idx (str): Request Index, typically a 6-digit integer.

    Returns:
        dict: filelist response, augmented with 'download_summary' so
              callers can verify files actually landed on disk before
              purging the request.
    """
    ret = get_filelist(request_idx)
    if len(ret['data']) == 0:
        ret['download_summary'] = {'expected': 0, 'downloaded': 0, 'complete': False}
        return ret

    filelist = ret['data']['web_files']

    web_files = list(map(lambda x: x['web_path'], filelist))

    # Only download unique files.
    unique_files = set(web_files)
    downloaded = download_files(unique_files, out_dir)
    ret['download_summary'] = {
        'expected': len(unique_files),
        'downloaded': len(downloaded),
        'complete': len(downloaded) == len(unique_files) and len(downloaded) > 0,
        'files': downloaded,
    }
    return ret

def globus_download(request_idx):
    """Begin a globus transfer.

    Args:
        request_ix (str): Request Index, typically a 6-digit integer.

    Returns:
        dict: JSON decoded result of the query.
    """
    url = BASE_URL + 'request/'
    url += request_idx
    url += '-globus_download'

    token = get_authentication()
    ret = requests.get(encode_url(url,token))

    check_status(ret)
    return ret.json()

def get_control_file_template(ds):
    """Write a control file for use in subset requests.

    Args:
        ds (str): datset id. e.g. 'ds083.2'

    Returns:
        dict: JSON decoded result of the query.
    """
    url = BASE_URL + 'control_file_template/'
    url += ds

    token = get_authentication()
    ret = requests.get(encode_url(url,token))

    check_status(ret)
    return ret.json()

def write_control_file_template(ds, write_location='./'):
    """Write a control file for use in subset requests.

    Args:
        ds (str): datset id. e.g. 'ds083.2'
        write_location (str, Optional): Directory in which to write.
                Defaults to working directory

    Returns:
        dict: JSON decoded result of the query.
    """
    _json = get_control_file_template(ds)
    control_str = _json['data']['template']

    template_filename = write_location + add_ds_str(ds) + '_control.ctl'
    if os.path.exists(template_filename):
        print(template_filename + " already exists.\nExiting")
        exit(1)
    with open(template_filename, 'w') as fh:
        fh.write(control_str)

    return _json

def purge_request(request_idx):
    """Purge a request from the RDA system.
    
    FIXED VERSION: Properly handles RDA's two-stage purge process:
    1. API call sets request to "Set for Purge" status (SUCCESS)
    2. RDA system automatically completes the purge later (AUTOMATIC)

    Args:
        request_idx (str): Request Index to purge (e.g., '804788')

    Returns:
        bool: True if purge was successfully initiated, False otherwise
    """
    import logging
    logger = logging.getLogger('rdams_purge_fix')
    
    try:
        url = BASE_URL + 'purge/'
        url += str(request_idx)

        token = get_authentication()
        ret = requests.delete(encode_url(url,token))

        check_status(ret)
        response = ret.json()
        
        # FIXED: Properly interpret RDA's purge responses
        if isinstance(response, dict):
            # SUCCESS CASE 1: Request already set for purge (this is SUCCESS, not failure!)
            if (response.get('status') == 'error' and
                response.get('http_response') == 442 and
                'already set for purge' in str(response.get('error_messages', [])).lower()):
                
                logger.info(f"✅ PURGE SUCCESS: Request {request_idx} is already set for purge")
                return True
            
            # SUCCESS CASE 2: Request newly set for purge
            elif response.get('status') == 'success' or 'success' in str(response).lower():
                logger.info(f"✅ PURGE SUCCESS: Request {request_idx} successfully set for purge")
                return True
            
            # ACTUAL ERROR CASES
            elif 'error' in response and 'not found' in str(response).lower():
                logger.error(f"❌ PURGE ERROR: Request {request_idx} not found")
                return False
            
            elif 'error' in response:
                error_msg = response.get('error_messages', ['Unknown error'])
                logger.error(f"❌ PURGE ERROR: {error_msg}")
                return False
            
            else:
                # Assume success if no clear error
                logger.info(f"✅ PURGE ASSUMED SUCCESS: Request {request_idx}")
                return True
        
        # For backward compatibility, return the response if not a dict
        return response
        
    except Exception as e:
        logger.error(f"❌ PURGE EXCEPTION: {e}")
        return False

def get_selected_function(args_dict):
    """Returns correct function based on options.
    Args:
        options (dict) : Command with options.

    Returns:
        (function): function that the options specified
    """
    # Maps an argument to function call
    action_map = {
            'get_summary' : get_summary,
            'get_metadata' : get_metadata,
            'get_param_summary' : get_param_summary,
            'submit' : submit,
            'get_status' : get_status,
            'download' : download,
            'get_filelist' : get_filelist,
            'globus_download' : globus_download,
            'get_control_file_template' : write_control_file_template,
            'purge' : purge_request
            }
    for opt,value in args_dict.items():
        if opt in action_map and value is not None:
            return (action_map[opt], value)


if __name__ == "__main__":
    """Calls main method"""
    query(sys.argv[1:])
