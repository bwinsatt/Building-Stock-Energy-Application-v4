// Map simplified names to file names
export type LogoName = keyof typeof nameToFile
export const nameToFile: Record<string, string> = {
  // Main logos
  'SiteLynx': 'sitelynx',
  'BlueLynx': 'bluelynx',
  'PLINK': 'plink',
  'PLINK Training': 'plink-training',
  'PLINK Testing': 'plink-testing',

  // Company logos
  'Partner': 'partner',
  'Partner ESI': 'partner-esi',
  'Partner Engineering and Science': 'partner-esi',
  'Partner Engineering and Science, Inc.': 'partner-esi',
  'Partner Energy': 'partner-energy',
  'Partner Valuation': 'partner-valuation',
  'Partner Valuation Advisors': 'partner-valuation',
  'Partner Property': 'partner-property',
  'Partner Property Consultants': 'partner-property',
  'Partner NCS': 'partner-ncs',
  'NCS Partner': 'partner-ncs',

  // Favicons
  'Favicon SiteLynx': 'favicon-sitelynx',
  'Favicon BlueLynx': 'favicon-bluelynx',
  'Favicon PLINK': 'favicon-plink',
  'Favicon Partner': 'favicon-partner',
  'SL': 'favicon-sitelynx',
  'BL': 'favicon-bluelynx',
  'PL': 'favicon-plink',
  'P': 'favicon-partner',
}

export const logoOptions: string[] = Object.keys(nameToFile)

