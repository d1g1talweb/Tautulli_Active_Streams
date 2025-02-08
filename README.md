# Tautulli Active Streams Integration for Home Assistant

A custom integration for Home Assistant that allows you to monitor active Plex streams using Tautulli Api.

## 📌 Features

- Dynamically creates session sensors based on active Plex streams.
- Monitor Active Plex Streams – See who’s watching and what they’re watching.
- Custom Sensor Count – Choose how many active streams to display.
- Adjustable Scan Interval – Set how often HA updates stream data.
- Detailed Session Attributes – Each active stream sensor provides:
    * :film_strip: **Media Title & Type** (Movie, TV Show, etc.)
    * :bust_in_silhouette: **User** (Who is watching)
    * :earth_africa: **IP Address & Device**
    * :tv: **Playback Progress & Quality**

---

:link: **GitHub:** [Tautulli Active Streams ](https://github.com/Richardvaio/Tautulli_Active_Streams)
:link: **Home-assistant Community:** (https://community.home-assistant.io/t/tautulli-active-streams-integration)


---

## **:inbox_tray: Installation**

:one: Install via [HACS](https://hacs.xyz/) or manually from GitHub.
:two: Add the integration in **Home Assistant → Settings → Devices & Services**.
:three: Enter your **Tautulli details (Url, API Key) Set Sensor Refresh and Count**.
:four: Display real-time stream data in **Lovelace cards!**

---

Give it a try and let me know what you think! :rocket:

---

## 🚀Custom Lovelace card
Produced by @stratotally and Edited by me.
Dynamically displays active Plex sessions using **Tautulli** data fetched by the `Tautulli Active Streams` integration.

1. **Install** `Tautulli Active Streams` integration via HACS or manually.
2. **Ensure Lovelace resources** for `button-card`, `bar-card`, `card-mod`, and `auto-entities` are loaded.
3. **Copy the YAML below** into your Lovelace dashboard.
4. **Enjoy real-time Plex session monitoring!** 🎬🔥

---

```
type: custom:auto-entities
filter:
  exclude:
    - state: unknown
    - state: unavailable
    - state: "off"
  include:
    - entity_id: "*plex*session*"
      options:
        entity: this.entity_id
        type: custom:button-card
        tap_action:
          action: none
        variables:
          entity: this.entity_id
        custom_fields:
          picture:
            card:
              type: picture
              image: |
                [[[
                  return states[variables.entity].attributes.image_url;
                ]]]
              card_mod:
                style: |
                  ha-card {
                    box-shadow: 0;
                    border-radius: 5px;
                    margin: 1px 3px -4px 3px;
                  }
                  ha-card img {
                    min-height: 80px;
                    min-width: 80px;
                  }
          bar:
            card:
              type: custom:bar-card
              entities:
                - entity: this.entity_id
              attribute: progress_percent
              unit_of_measurement: "%"
              positions:
                icon: "off"
                indicator: "off"
                name: inside
              height: 19px
              color: |
                [[[
                  if (states[variables.entity].state == 'playing') {
                    return '#2986cc';
                  } else if (states[variables.entity].state == 'paused') {
                    return '#e49f29; animation: blink 1.5s linear infinite;'; 
                  } else {
                    return '#000000'; // Default color if neither playing nor paused
                  }
                ]]]      
              name: |
                [[[
                  return states[variables.entity].state
                ]]]
              card_mod:
                style: |-
                  @keyframes blink {
                    50% {
                     opacity: 0;
                    }
                  }
                  ha-card {
                    --ha-card-background: rgba(0, 0, 0, 0.8) !important;
                    border: 0.02px solid rgba(70, 130, 180, 0.3);

                    box-shadow: none;
                  }
                  ha-card #states {
                    padding: 0;
                  }
                  bar-card-currentbar, bar-card-backgroundbar {
                    border-radius: 8px;
                    left: 0;
                  }
                  bar-card-name {
                    margin-left: 3%;
                    text-shadow: 1px 1px 1px #0003;
                  }
                  bar-card-value {
                    margin-right: 3%;
                    text-shadow: 1px 1px 1px #0003;
                  }
          user: |
            [[[
              return "<b>" + states[variables.entity].attributes.user + "</b>"
            ]]]
          title: |
            [[[
              if (states[variables.entity].state == 'playing') {
                return "<ha-icon icon='mdi:play' style='width: 15px; height: 15px; position: relative; top: -2px;'></ha-icon> " + states[variables.entity].attributes.full_title;
              } else {
                if (states[variables.entity].state == 'paused') {
                  return "<ha-icon icon='mdi:pause' style='width: 15px; height: 15px; position: relative; top: -2px;'></ha-icon> " + states[variables.entity].attributes.full_title;
                } else {
                  return states[variables.entity].attributes.full_title;
                }
              }

            ]]]
          stream: |
            [[[
              return states[variables.entity].attributes.transcode_decision + " - " + states[variables.entity].attributes.stream_video_resolution;
            ]]]
          product: |
            [[[
              var player = states[variables.entity].attributes.player;
              var product = states[variables.entity].attributes.product;
              return product + ' - ' + '<i>' + player + '</i>';
            ]]]
          media_detail: |
            [[[
              if(states[variables.entity].attributes.media_type == 'movie') {
                return "<ha-icon icon='mdi:filmstrip' style='width: 15px; height: 15px; position: relative; top: -2px;'></ha-icon> (" + states[variables.entity].attributes.year + ")";
              } else {
                return "<ha-icon icon='mdi:television-classic' style='width: 15px; height: 15px; position: relative; top: -2px;'></ha-icon> S" + states[variables.entity].attributes.parent_media_index + " • E" + states[variables.entity].attributes.media_index;
              }
            ]]]
          bandwidth: |
            [[[ 
              var bytes = states[variables.entity].attributes.bandwidth * 1000;
              var sizes = ['Bytes', 'Kbps', 'Mbps', 'Gbps', 'Tbps'];
              if (bytes == 0) return 'n/a';
              var i = parseInt(Math.floor(Math.log(bytes) / Math.log(1000)));
              if (i == 0) return 'Bandwidth: ' + bytes + ' ' + sizes[i];
              return 'Bandwidth: ' + (bytes / Math.pow(1000, i)).toFixed(1) + ' ' + sizes[i];
            ]]]
        card_mod:
          style: |
            ha-card {
              padding: 0;
              margin: 0;
              border: 0.01px solid rgba(70, 130, 180, 0.5);
              box-shadow: 3px 3px 5px rgba(0, 0, 0, 0.5); /* Add a box shadow effect */
              background: rgba(0.40, 1, 0, 0.5) !important;
            }
            ha-card #container {
            margin: 5px 0 0 0;

            }
            #name {
              display:none;
            }
        styles:
          card:
            - height: 100x
            - padding: 0
          custom_fields:
            bar:
              - text-transform: capitalize
              - font-size: 13px
              - padding-top: 2px
              - padding-bottom: 0px
            user:
              - text-transform: capitalize
              - text-align: end
              - font-size: 12px
              - font-family: Arial, sans-serif;
              - font-style: italic;
              - letter-spacing: 2px;
              - margin-left: "-60px;"
            title:
              - text-transform: capitalize
              - text-align: start
              - font-size: 26px
              - margin-top: "-5px"
              - margin-bottom: 2px
            stream:
              - text-transform: capitalize
              - text-align: start
              - font-size: 12px
            product:
              - text-transform: capitalize
              - text-align: start
              - font-size: 12px
            media_detail:
              - text-transform: uppercase
              - text-align: start
              - font-size: 15px
            bandwidth:
              - text-transform: capitalize
              - text-align: end
              - font-size: 12px
              - margin-left: "-60px;"
          grid:
            - grid-template-areas: |
                "picture product user"
                "picture title title"    
                "picture media_detail media_detail"
                "picture bar bar"
                "picture stream bandwidth"
            - grid-template-columns: 1fr 200px 3fr
            - grid-gap: 5px 3px
card:
  type: vertical-stack
card_param: cards
```

---

## 🛠 Troubleshooting

### No Data Appearing?

- Ensure your **Tautulli API key, Url** are correct.
- Restart Home Assistant after making changes.
- Check **Developer Tools** → **States** for `sensor.plex_session_*`.

---

## 🤝 Contributing
Want to improve this integration? Feel free to submit a PR or open an issue on GitHub!

---

## 📜 License
This project is licensed under the MIT License.

---


Changelog - Tautulli Active Streams

v2.0.1 - (08.02.2025)
- Switched to full URL input instead of separate host/port.
- Added SSL verification option for self-signed certificates.
- Improved reverse proxy support with proper URL handling.
- Fixed image proxy URLs to remove API key exposure.
- Optimized sensor updates & reload handling.
- Improved logging & error handling for better troubleshooting.
- Now respects X-Forwarded-Proto headers for proxy setups.

Update via HACS or GitHub & restart Home Assistant!
