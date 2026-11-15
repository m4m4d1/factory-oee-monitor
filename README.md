# Factory Production Monitoring (OEE)

**Pemantauan Produksi Pabrik (OEE)** for Indonesian industrial estates.

Monitors production lines in Indonesian industrial estates: output, downtime, quality and Overall
Equipment Effectiveness (OEE) per line and shift, with a downtime Pareto and alerts when a line's
shift falls below 65% OEE or a line stops for more than 30 minutes.

> Week 4 of Nusantara Intel: one new open-source
> information system for Indonesia every week, built in public one step per day.

## Plants and lines

7 plants with 19 lines in real industrial estates. **The company names are fictional** and every
production figure is simulated, so nothing here describes a real factory.

| Plant (fictional) | Estate | City | Lines |
|-------------------|--------|------|-------|
| PT Sinar Logam Presisi | KIIC | Karawang | press line A, press line B, robot welding cell |
| PT Arunika Plastindo | Suryacipta City of Industry | Karawang | moulding 350 t, moulding 650 t, assembly |
| PT Embun Pagi Minuman | Kawasan Industri Jababeka | Cikarang | PET filling, cup filling, gallon line |
| PT Pilar Baja Pipa | MM2100 | Cikarang Barat | ERW pipe mill, threading line |
| PT Selat Elektronika Presisi | Batamindo Industrial Park | Batam | SMT line 1, SMT line 2, box build |
| PT Delta Kemasan Timur | JIIPE | Gresik | corrugator, film bag line |
| PT Lintang Busana Jaya | Kawasan Industri Terpadu Batang | Batang | sewing line A, sewing line B, finishing & packing |

## What is measured

| Factor | Formula | Loss it shows |
|--------|---------|---------------|
| Availability | run time / planned production time | stops: breakdowns, changeovers, shortages, outages |
| Performance | ideal cycle time × total count / run time | running slower than the rated speed |
| Quality | good count / total count | scrap and rework |
| **OEE** | availability × performance × quality | all three together |

Three shifts (07:00-15:00, 15:00-23:00 and 23:00-07:00 WIB), each with 420 minutes of planned
production time after a 60-minute meal break. 85% OEE is the commonly cited world-class level and
65% a common floor; these are industry conventions from TPM, not regulations.

## Roadmap this week

- [x] Mon: scaffold, plants, lines and data model
- [ ] Tue: production simulator and storage
- [ ] Wed: REST API, OEE calculation and alerts
- [ ] Thu: dashboard
- [ ] Fri: plant map and alerts panel
- [ ] Sat: Docker, tests and documentation
- [ ] Sun: live demo and v1.0 release

## License

MIT
