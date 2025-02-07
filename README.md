# Tautulli Active Streams Integration for Home Assistant

A custom integration for Home Assistant that allows you to monitor active Plex streams using Tautulli Api.

## 📌 Features

- Dynamically creates session sensors based on active Plex streams.
- Supports multiple concurrent streams with dynamic updates.
- Fetches real-time stream data (e.g., user, title, player, quality, bandwidth, etc.).
- Customizable scan interval and number of session sensors.


## 🚀 Installation via HACS

  1. Open **HACS** in Home Assistant.
  2. Go to **Integrations** → **+ Explore & Download Repositories**.
  3. Click the **three-dot menu** (⋮) in the top-right and select **Custom repositories**.
  4. Add the following repository URL: https://github.com/Richardvaio/Tautulli_Active_Streams
     - Select **Integration** as the category.
     - Click **Add**.

  5. Find **Tautulli Active Streams** in HACS and install it.
  6. Restart Home Assistant.



## 🔧 Configuration

  1. Go to **Settings** → **Devices & Services**.
  2. Click **+ Add Integration** → Select **Tautulli Active Streams**.
  3. Enter your **Tautulli API details** (Host, Port, API Key).
  4. Set the **interval refresh rate** (default: 10 seconds).
  5. Set the **maximum number of session sensors** (default: 5).
  6. Click **Submit**.



## 🔄 Updating

To update the integration:

  1. Go to **HACS** → **Integrations**.
  2. Find **Tautulli Active Streams** and click **Update** (if available).
  3. Restart Home Assistant.

## 🛠 Troubleshooting

### No Data Appearing?

- Ensure your **Tautulli API key, host, and port** are correct.
- Restart Home Assistant after making changes.
- Check **Developer Tools** → **States** for `sensor.plex_session_*`.



## 🤝 Contributing
Want to improve this integration? Feel free to submit a PR or open an issue on GitHub!



## 📜 License
This project is licensed under the MIT License.
