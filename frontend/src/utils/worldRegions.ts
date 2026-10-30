/**
 * The world region of every country in our country list (migration
 * 0012_load_countries, as named in registration/timeZoneCountries.ts), for the
 * Users page's world map and its region totals. The map and the totals read
 * this one table, so a country coloured on the map is always counted in its
 * region. Russia and Turkey count as Asia, where the map draws them.
 */

export const WORLD_REGIONS = ['North America', 'South America', 'Europe', 'Africa', 'Asia', 'Oceania'] as const
export type WorldRegion = (typeof WORLD_REGIONS)[number]

const COUNTRIES_BY_REGION: Record<WorldRegion, readonly string[]> = {
  'North America': [
    'Antigua and Barbuda', 'Bahamas', 'Barbados', 'Belize', 'Canada', 'Costa Rica', 'Cuba',
    'Dominica', 'Dominican Republic', 'El Salvador', 'Grenada', 'Guatemala', 'Haiti', 'Honduras',
    'Jamaica', 'Mexico', 'Nicaragua', 'Panama', 'Saint Kitts and Nevis', 'Saint Lucia',
    'Saint Vincent and the Grenadines', 'Trinidad and Tobago', 'United States of America',
  ],
  'South America': [
    'Argentina', 'Bolivia', 'Brazil', 'Chile', 'Colombia', 'Ecuador', 'Guyana', 'Paraguay', 'Peru',
    'Suriname', 'Uruguay', 'Venezuela',
  ],
  'Europe': [
    'Albania', 'Andorra', 'Austria', 'Belarus', 'Belgium', 'Bosnia and Herzegovina', 'Bulgaria',
    'Croatia', 'Czechia (Czech Republic)', 'Denmark', 'Estonia', 'Finland', 'France', 'Germany',
    'Greece', 'Holy See', 'Hungary', 'Iceland', 'Ireland', 'Italy', 'Latvia', 'Liechtenstein',
    'Lithuania', 'Luxembourg', 'Malta', 'Moldova', 'Monaco', 'Montenegro', 'Netherlands',
    'North Macedonia', 'Norway', 'Poland', 'Portugal', 'Romania', 'San Marino', 'Serbia',
    'Slovakia', 'Slovenia', 'Spain', 'Sweden', 'Switzerland', 'Ukraine', 'United Kingdom',
  ],
  'Africa': [
    'Algeria', 'Angola', 'Benin', 'Botswana', 'Burkina Faso', 'Burundi', 'Cabo Verde', 'Cameroon',
    'Central African Republic', 'Chad', 'Comoros', 'Congo (Congo-Brazzaville)', 'Côte d\'Ivoire',
    'Democratic Republic of the Congo', 'Djibouti', 'Egypt', 'Equatorial Guinea', 'Eritrea',
    'Eswatini (fmr. ""Swaziland"")', 'Ethiopia', 'Gabon', 'Gambia', 'Ghana', 'Guinea',
    'Guinea-Bissau', 'Kenya', 'Lesotho', 'Liberia', 'Libya', 'Madagascar', 'Malawi', 'Mali',
    'Mauritania', 'Mauritius', 'Morocco', 'Mozambique', 'Namibia', 'Niger', 'Nigeria', 'Rwanda',
    'Sao Tome and Principe', 'Senegal', 'Seychelles', 'Sierra Leone', 'Somalia', 'South Africa',
    'South Sudan', 'Sudan', 'Tanzania', 'Togo', 'Tunisia', 'Uganda', 'Zambia', 'Zimbabwe',
  ],
  'Asia': [
    'Afghanistan', 'Armenia', 'Azerbaijan', 'Bahrain', 'Bangladesh', 'Bhutan', 'Brunei', 'Cambodia',
    'China', 'Cyprus', 'Georgia', 'India', 'Indonesia', 'Iran', 'Iraq', 'Israel', 'Japan', 'Jordan',
    'Kazakhstan', 'Kuwait', 'Kyrgyzstan', 'Laos', 'Lebanon', 'Malaysia', 'Maldives', 'Mongolia',
    'Myanmar (formerly Burma)', 'Nepal', 'North Korea', 'Oman', 'Pakistan', 'Palestine State',
    'Philippines', 'Qatar', 'Russia', 'Saudi Arabia', 'Singapore', 'South Korea', 'Sri Lanka',
    'Syria', 'Tajikistan', 'Thailand', 'Timor-Leste', 'Turkey', 'Turkmenistan',
    'United Arab Emirates', 'Uzbekistan', 'Vietnam', 'Yemen',
  ],
  'Oceania': [
    'Australia', 'Fiji', 'Kiribati', 'Marshall Islands', 'Micronesia', 'Nauru', 'New Zealand',
    'Palau', 'Papua New Guinea', 'Samoa', 'Solomon Islands', 'Tonga', 'Tuvalu', 'Vanuatu',
  ],
}

/** Countries the map labels by a shorter name than the country list does. */
export const MAP_COUNTRY_NAMES: Record<string, string> = {
  'United States of America': 'United States',
  'Czechia (Czech Republic)': 'Czechia',
  'Myanmar (formerly Burma)': 'Myanmar',
}

const regionByCountry = new Map<string, WorldRegion>([
  ...WORLD_REGIONS.flatMap((region) => COUNTRIES_BY_REGION[region].map((name) => [name, region] as const)),
  // The map draws Greenland, which is not in the country list.
  ['Greenland', 'North America'],
])
for (const [listName, mapName] of Object.entries(MAP_COUNTRY_NAMES)) {
  regionByCountry.set(mapName, regionByCountry.get(listName)!)
}

/** The map's name for a country-list name; other names are returned unchanged. */
export const mapCountryName = (name: string): string => MAP_COUNTRY_NAMES[name] ?? name

/** The world region of a country, by its country-list or map name; null when unknown. */
export const worldRegionForCountry = (name: string | null | undefined): WorldRegion | null =>
  name ? (regionByCountry.get(name) ?? null) : null
