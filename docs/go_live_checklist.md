# Go-live checklist

Switch to real money only when every box is ticked.

- [ ] The bot has run on demo for at least 4 weeks (8 is better) with no unexplained errors
- [ ] At least 30 demo trades, with results inside the range the backtest predicted
- [ ] Real commission and slippage matched config/contract_specs.yaml
- [ ] The daily loss limit, kill switch, /pause and /stop were each tested on demo and worked
- [ ] The bot recovered from a VPS reboot and a network drop without duplicate trades
- [ ] Phase 2 was re-run against the real account to confirm its costs and minimum stake
- [ ] A real-account PAT is created and stored only in the VPS .env, with DERIV_MODE=real and the real account ID
- [ ] Only money I can afford to lose is deposited, and the bot starts at the smallest stake
- [ ] Stop rule agreed: if the live drawdown passes the worst backtest drawdown, pause and review before trading again
