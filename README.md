# vk-helpers

✨ VKontakte Utility CLI for archive data that allows you to delete all comments or download images from albums really fast.

## Overview

This project provides a command-line interface (CLI) utility for managing VKontakte (VK) data in two main modes:
1. Downloading image albums.
2. Deleting comments from wall posts.

## Features

- **ImageDownloader**: Downloads images from an HTML file containing image links.
- **CommentDeleter**: Deletes comments on wall posts based on provided HTML files.

## Installation

To use this utility, you need to have Python installed. Install the required packages using the following command:

```bash
pip install -r requirements.txt
```

Before executing the script make sure that you have downloaded your archive with comments and photos export enabled.
You can request VK archive [here](https://vk.com/data_protection?section=rules&scroll_to_archive=1)


## Usage

### Running the CLI

Execute the script via a terminal:

```bash
python cli.py
```

You will be prompted to select a mode and provide necessary inputs.

### Modes

#### Mode 1: Download Images from Album

1. **Input File**: Path to the HTML file containing the images.
2. **Output Directory**: The directory where images will be saved.
3. **Batch Size**: Number of images to download per batch.
4. **Encoding**: The file encoding of the HTML file. (default: `windows-1251`)
5. **Retries**: Number of retries for downloading an image.

#### Mode 2: Delete Comments

1. **Input Directory**: Directory containing the HTML files from which to extract wall IDs for comment deletion.
2. **Output File**: File where the extracted wall IDs will be stored.
3. **Access Token**: VK API access token for deleting comments.
4. **Exclude IDs**: Group/User IDs to exclude from deletion.
5. **Sleep Time**: Time to wait between API requests.

## Example

### Download Images

To download images:
1. Place your HTML file in a known location.
2. Run the script and select mode `1`.
3. Provide the path to your HTML file, desired output directory, batch size, encoding, and number of retries.

### Delete Comments

To delete comments:
1. Gather HTML files containing wall IDs in a directory.
2. Run the script and select mode `2`.
3. Provide the path to your input directory, desired output file, VK API access token, any exclude IDs, and sleep time between requests.

## Example Usage
```
Select mode that you want to use:
[1] Download album
[2] Delete all comments
Enter the number corresponding to the mode: 
```

Follow through with the appropriate prompts based on your selected mode.

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

[MIT](https://opensource.org/licenses/MIT)

---

By contributing to this project, you agree to abide by its terms and conditions.