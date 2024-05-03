import { base, baseSepolia } from "viem/chains";
import { IRevolutionConfig } from "../interfaces";

const config: IRevolutionConfig = {
  revolutionToken: {
    address: // "0xebf2d8b25d3dcc3371d54c6727c207c4f3080b8c", // token contract address, to be edited after deployment
    chainId: base.id,
  },
  auctionLaunchTime: new Date("2024-04-08T23:00:00.000Z"),
  auctionPreLaunchPlaceholderImage: // To be added before 1st auction: "https://i.imgur.com/QZ0ST0M.png",
  darkMode: false,
  name: "DurianDAO",
  homepageRedirect: "auction",
  votesShortName: "pulp",
  aboutBackgroundPattern: // To be added as background pattern "/images/grounds/grounds_pattern.png",
  missionBackgroundPattern: // to be added as another section's image background "https://i.imgur.com/NyPlMYv.jpeg",
  missionIllustration: // hero image for mission "/images/grounds/mission_illustration.jpg",
  url: // buy a domain "groundsdao.wtf",
  logoUrl: // logo  "/images/grounds/logo.svg",
  faviconUrl: // Favicon "/images/grounds/logo_square.png",
  socialLinks: {
    twitter: "https://twitter.com/DurianDaolol",
    telegram: "https://t.me/duriandao",
  },
  font: "Roboto Mono",
  creationsDefaultView: "grid",
  hiddenMenuItems: ["stories", ""],
  customMenuItems: [
    { url: "creations", name: "Art Race", icon: null },
    // { url: "grants", name: "Grants", icon: null },
    // { url: "build", name: "Let's Build", icon: null },
  ],
  landingPage: {
    tagline: // come up with tagline "Wake up! Be bold, pour freely, and brew good.",
    baseDomain: // add domain "grounds.build",
    backdropImage: // to be updated "/images/grounds/mission_illustration.jpg",
  },
  colorPalette: { lead: "yellow", secondary: "green" },
  backgroundPattern: null,
  backgroundColor: "#fff",
  cardColor: "#fafafa",
  hashtag: "groundish",
  palette: {
    light: {
      background: "#fff",
      card: "#fafafa",
      lead: "red",
      secondary: "brown",
    },
    dark: {
      background: "#18181b",
      card: "#27272a",
      lead: "red",
      secondary: "brown",
    },
  },
  defaultSeo: {
    title: "Durian DAO",
    description: // Add description "Wake up! Be bold, pour freely, and brew good.",
  },
  creationMethods: ["upload"],
};

export default config;