import asyncio
import os
import re
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup
from colorama import init, Fore, Style
from tqdm import tqdm
from typing import Union, List, Dict, Tuple

init()

class ImageDownloader:

    def __init__(self, output_dir: str, batch_size: int, retries: int, encoding: str):
        self.output_dir = output_dir
        self.batch_size = batch_size
        self.retries = retries
        self.encoding = encoding

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        return re.sub(r'[<>:"/\\|?*]', '', filename)

    @staticmethod
    def get_filename_from_url(url: str) -> str:
        path = urlparse(url).path
        filename = os.path.basename(path)
        return ImageDownloader.sanitize_filename(filename)

    async def download_image(self, client: httpx.AsyncClient, img_url: str, img_name: str):
        attempt = 0
        while attempt < self.retries:
            try:
                response = await client.get(img_url)
                if response.status_code == 200:
                    with open(os.path.join(self.output_dir, img_name), "wb") as img_file:
                        img_file.write(response.content)
                    return
                else:
                    print(f"{Fore.RED} Failed to download: {img_url} (status code: {response.status_code}){Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.RED} Error downloading {img_url}: {str(e)}{Style.RESET_ALL}")

            attempt += 1
            if attempt < self.retries:
                print(f"{Fore.YELLOW} Retrying {img_url} in 2 seconds... (Attempt {attempt + 1}){Style.RESET_ALL}")
                await asyncio.sleep(2)

    async def process_batch(self, batch: List[BeautifulSoup], pbar: tqdm):
        async with httpx.AsyncClient() as client:
            tasks = [
                self.download_image(client, img["src"], self.get_filename_from_url(img["src"]))
                for img in batch
            ]
            await asyncio.gather(*tasks)
            pbar.update(len(batch))

    async def download_images(self, input_file: str) -> None:
        with open(input_file, "r", encoding=self.encoding) as file:
            html_content = file.read()

        soup = BeautifulSoup(html_content, "html.parser")
        img_tags = soup.find_all("img")

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        with tqdm(total=len(img_tags), desc="Downloading images", unit="img") as pbar:
            for i in range(0, len(img_tags), self.batch_size):
                batch = img_tags[i:i + self.batch_size]
                await self.process_batch(batch, pbar)

        print(f"{Fore.GREEN}All images have been downloaded.{Style.RESET_ALL}")


class CommentDeleter:
    def __init__(self, access_token: str, sleep_time: float, exclude_ids: List[str]):
        self.access_token = access_token
        self.sleep_time = sleep_time
        self.exclude_ids = exclude_ids

    @staticmethod
    def parse_html_file(file_path: str, wall_ids: List[str]) -> None:
        with open(file_path, 'r', encoding='windows-1251') as file:
            content = file.read()
            soup = BeautifulSoup(content, 'lxml')
            item_main_divs = soup.find_all('div', class_='item__main')
            for div in item_main_divs:
                links = div.find_all('a')
                for link in links:
                    href = link.get('href')
                    if href and 'wall' in href:
                        wall_id = href.split('/')[-1]
                        wall_ids.append(wall_id)

    @staticmethod
    def extract_comment_details(wall_id: str) -> Tuple[str, str]:
        parts = wall_id.split('_')
        owner_id = parts[0].replace('wall', '')
        if '?reply=' in parts[1]:
            comment_id = parts[1].split('?reply=')[1].split("&")[0]
        else:
            comment_id = parts[1].split('?')[0]
        return owner_id, comment_id

    @staticmethod
    def chunk_list(lst: List[str], chunk_size: int):
        for i in range(0, len(lst), chunk_size):
            yield lst[i:i + chunk_size]

    def build_vk_execute_code(self, wall_ids: List[str]) -> List[str]:
        execute_commands = []
        for batch in self.chunk_list(wall_ids, 25):
            execute_code = [
                f'API.wall.deleteComment({{"owner_id": {self.extract_comment_details(wall_id)[0]}, "comment_id": {self.extract_comment_details(wall_id)[1]}}})'
                for wall_id in batch
            ]
            execute_commands.append(f'return [{",".join(execute_code)}];')
        return execute_commands

    async def execute_vk_command(self, command: str) -> Dict:
        url = "https://api.vk.com/method/execute"
        params = {
            "access_token": self.access_token,
            "v": "5.131",
            "code": command
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)

        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()

    async def delete_comments(self, input_dir: str, output_file: str) -> None:
        wall_ids = []

        for filename in os.listdir(input_dir):
            if filename.endswith('.html'):
                self.parse_html_file(os.path.join(input_dir, filename), wall_ids)

        filtered_wall_ids = [
            wall_id for wall_id in wall_ids 
            if not any(exclude_id in wall_id.split('_')[0] for exclude_id in self.exclude_ids)
        ]

        with open(output_file, 'w', encoding='utf-8') as file:
            for wall_id in filtered_wall_ids:
                file.write(wall_id + '\n')

        print(f"{Fore.GREEN}Extracted {len(filtered_wall_ids)} wall IDs to {output_file}{Style.RESET_ALL}")

        print(f"{Fore.YELLOW}Review the wall IDs in file {output_file} that will be deleted.{Style.RESET_ALL}")
        proceed = input(f"{Fore.CYAN}Do you want to proceed with the deletion (yes/no)? {Style.RESET_ALL}")

        if proceed.lower() != 'yes':
            print(f"{Fore.RED}Deletion process aborted by the user.{Style.RESET_ALL}")
            return

        execute_codes = self.build_vk_execute_code(filtered_wall_ids)

        total_successful = 0
        total_failed = 0

        with tqdm(total=len(execute_codes), desc="Deleting comments", unit="batch") as pbar:
            for command in execute_codes:
                result = await self.execute_vk_command(command)
                if 'response' in result:
                    successful = result['response'].count(True)
                    failed = result['response'].count(False)
                    total_successful += successful
                    total_failed += failed
                    print(f"{Fore.GREEN} Successfully deleted {successful} comments; {Fore.YELLOW}Failed to delete {failed} comments (possibly already deleted or in closed group/page).{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}Error in API response: {result}{Style.RESET_ALL}")
                await asyncio.sleep(self.sleep_time)
                pbar.update(1)

        print(f"\n{Fore.GREEN}Final Summary:{Style.RESET_ALL}")
        print(f"{Fore.GREEN}Successfully deleted {total_successful} comments in total.{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Failed to delete {total_failed} comments in total (possibly already deleted or in closed group/page).{Style.RESET_ALL}")


class Validator:

    @staticmethod
    def validate_input_dir(input_dir: str, mode: str) -> str:
        input_dir = input_dir.strip('"')
        if not os.path.exists(input_dir):
            raise ValueError(f"{Fore.RED}The specified input path does not exist.{Style.RESET_ALL}")

        if mode == '1' and not input_dir.lower().endswith('.html'):
            raise ValueError(f"{Fore.RED}For mode 1, input_dir should be a single .html file.{Style.RESET_ALL}")
        elif mode == '2':
            if not os.path.isdir(input_dir):
                raise ValueError(f"{Fore.RED}For mode 2, input_dir should be a directory containing .html files, not a specific file.{Style.RESET_ALL}")
            html_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.html')]
            if not html_files:
                raise ValueError(f"{Fore.RED}The input directory for mode 2 should contain at least one .html file.{Style.RESET_ALL}")

        return input_dir

    @staticmethod
    def validate_output_dir(output_dir: str) -> None:
        if os.path.exists(output_dir) and not os.path.isdir(output_dir):
            raise ValueError(f"{Fore.RED}The specified output path exists but is not a directory.{Style.RESET_ALL}")

    @staticmethod
    def validate_batch_size(batch_size: Union[str, int]) -> int:
        try:
            batch_size = int(batch_size)
            if batch_size <= 0:
                raise ValueError
        except ValueError:
            raise ValueError(f"{Fore.RED}Batch size must be a positive integer.{Style.RESET_ALL}")
        return batch_size

    @staticmethod
    def validate_retries(retries: Union[str, int]) -> int:
        try:
            retries = int(retries)
            if retries < 0:
                raise ValueError
        except ValueError:
            raise ValueError(f"{Fore.RED}Number of retries must be a non-negative integer.{Style.RESET_ALL}")
        return retries

    @staticmethod
    def validate_sleep_time(sleep_time: Union[str, float]) -> float:
        try:
            sleep_time = float(sleep_time)
            if sleep_time < 0:
                raise ValueError
        except ValueError:
            raise ValueError(f"{Fore.RED}Sleep time must be a non-negative number.{Style.RESET_ALL}")
        return sleep_time


async def main():
    print(f"{Fore.CYAN}Select mode that you want to use:{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}[1] Download album{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}[2] Delete all comments{Style.RESET_ALL}")
    mode = input(f"{Fore.CYAN}Enter the number corresponding to the mode: {Style.RESET_ALL}")

    if mode not in ['1', '2']:
        print(f"{Fore.RED}Invalid selection. Please choose either 1 or 2.{Style.RESET_ALL}")
        return

    try:
        if mode == '1':
            input_file = input(f"{Fore.CYAN}Enter the path to the HTML file containing the images: {Style.RESET_ALL}")
            input_file = Validator.validate_input_dir(input_file, mode)

            output_dir = input(f"{Fore.CYAN}Enter the directory to save downloaded images (default: downloaded_images): {Style.RESET_ALL}") or "downloaded_images"
            Validator.validate_output_dir(output_dir)

            batch_size = input(f"{Fore.CYAN}Enter the number of images to download at a time (default: 50): {Style.RESET_ALL}") or 50
            batch_size = Validator.validate_batch_size(batch_size)

            encoding = input(f"{Fore.CYAN}Enter the encoding of the HTML file (default: windows-1251): {Style.RESET_ALL}") or "windows-1251"

            retries = input(f"{Fore.CYAN}Enter the number of retries for downloading an image (default: 3): {Style.RESET_ALL}") or 3
            retries = Validator.validate_retries(retries)

            downloader = ImageDownloader(output_dir, batch_size, retries, encoding)
            await downloader.download_images(input_file)

        elif mode == '2':
            input_dir = input(f"{Fore.CYAN}Enter the directory containing the HTML files for comment deletion: {Style.RESET_ALL}")
            input_dir = Validator.validate_input_dir(input_dir, mode)

            output_file = input(f"{Fore.CYAN}Enter the output file to store the extracted wall ID (default: to_delete_comment_ids.txt): {Style.RESET_ALL}") or "to_delete_comment_ids.txt"
            access_token = input(f"{Fore.CYAN}Enter the VK API access token for deleting comments: {Style.RESET_ALL}")

            if not access_token:
                raise ValueError(f"{Fore.RED}Error: access_token is required for deleting comments.{Style.RESET_ALL}")

            exclude_ids = input(f"{Fore.CYAN}Enter group/user IDs to exclude (comma-separated, e.g., -108958540,182582439): {Style.RESET_ALL}")
            exclude_ids = [id.strip() for id in exclude_ids.split(',') if id.strip()]

            sleep_time = input(f"{Fore.CYAN}Enter the sleep time between API requests in seconds (default: 1): {Style.RESET_ALL}") or 1
            sleep_time = Validator.validate_sleep_time(sleep_time)

            deleter = CommentDeleter(access_token, sleep_time, exclude_ids)
            await deleter.delete_comments(input_dir, output_file)

    except ValueError as e:
        print(f"{Fore.RED}{str(e)}{Style.RESET_ALL}")

    finally:
        input(f"{Fore.CYAN}Press Enter to exit...{Style.RESET_ALL}")


if __name__ == "__main__":
    asyncio.run(main())
