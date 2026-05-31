export type LocationPreset = {
  label: string;
  latitude: string;
  longitude: string;
  region: string;
};

export const locationPresets: LocationPreset[] = [
  {
    label: "Seoul",
    latitude: "37.5665",
    longitude: "126.9780",
    region: "Korea",
  },
  {
    label: "Tokyo",
    latitude: "35.6762",
    longitude: "139.6503",
    region: "Japan",
  },
  {
    label: "San Francisco",
    latitude: "37.7749",
    longitude: "-122.4194",
    region: "US West",
  },
  {
    label: "Reykjavik",
    latitude: "64.1466",
    longitude: "-21.9426",
    region: "North Atlantic",
  },
];
